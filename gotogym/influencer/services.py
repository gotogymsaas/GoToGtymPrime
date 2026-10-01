"""Logica de negocio del programa de afiliados: aprobacion, comisiones y
retiros. Los servicios de `orders` llaman a las funciones de comision
(`register_order_commission`, `approve_order_commission`,
`revert_order_commission`) al cambiar el estado de un pedido; esta app
nunca importa nada de `orders` a nivel de modulo para evitar un ciclo,
salvo dentro de las funciones que lo necesitan (import diferido).
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Commission,
    CommissionStatus,
    InfluencerProgramSettings,
    InfluencerStatus,
    WithdrawalRequest,
    WithdrawalStatus,
)


def get_commission_rate(profile):
    if profile.commission_rate is not None:
        return profile.commission_rate
    return InfluencerProgramSettings.load().default_commission_rate


def recompute_profile_totals(profile):
    """Recalcula los contadores que ve el afiliado en su panel a partir de
    los pedidos y comisiones reales, en vez de confiar en que algun otro
    punto del codigo los haya incrementado a mano."""
    from orders.models import PaymentStatus  # evita el ciclo orders <-> influencer

    pedidos_referidos = profile.referred_orders.filter(payment_status=PaymentStatus.APPROVED)
    profile.total_referred = pedidos_referidos.count()
    profile.total_sales = pedidos_referidos.aggregate(total=Sum('subtotal'))['total'] or Decimal('0.00')
    # Solo cuenta como "disponible" lo aprobado y no ligado aun a una
    # solicitud de retiro: lo pendiente todavia esta en periodo de
    # devolucion, y lo ya ligado esta a la espera de pago.
    profile.commission_balance = profile.commissions.filter(
        status=CommissionStatus.APPROVED, withdrawal_request__isnull=True,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    profile.save(update_fields=['total_referred', 'total_sales', 'commission_balance'])


def register_order_commission(order):
    """Crea la comision pendiente de un pedido referido cuando su pago
    queda aprobado. Idempotente: si el pedido ya tiene comision (doble
    aviso de pago) no la duplica."""
    if not order.referred_by_id or Commission.objects.filter(order=order).exists():
        return None
    profile = order.referred_by
    tasa = get_commission_rate(profile)
    # Base neta (subtotal menos descuento del propio cupon): decision de
    # negocio del sistema propuesto, no un dato que el benchmarking fije.
    base = order.subtotal - order.discount_total
    monto = (base * tasa / Decimal('100')).quantize(Decimal('0.01'))
    comision = Commission.objects.create(influencer=profile, order=order, amount=monto)
    recompute_profile_totals(profile)
    return comision


def approve_order_commission(order):
    """Pasa a aprobada la comision de un pedido que llego a entregado: ya
    supero la ventana en la que podria devolverse."""
    try:
        comision = order.commission
    except Commission.DoesNotExist:
        return
    if comision.status == CommissionStatus.PENDING:
        comision.status = CommissionStatus.APPROVED
        comision.save(update_fields=['status', 'updated_at'])
        recompute_profile_totals(comision.influencer)


def revert_order_commission(order):
    """Revierte la comision si el pedido se cancela o se devuelve."""
    try:
        comision = order.commission
    except Commission.DoesNotExist:
        return
    if comision.status in (CommissionStatus.PENDING, CommissionStatus.APPROVED):
        comision.status = CommissionStatus.REVERTED
        comision.save(update_fields=['status', 'updated_at'])
        recompute_profile_totals(comision.influencer)


def _ensure_personal_coupon(profile):
    """Genera (o reactiva) el cupon personal del afiliado: el mismo codigo
    que ve en su panel (`referral_code`) queda utilizable en el checkout."""
    from orders.models import Coupon, CouponDiscountType

    existente = profile.coupons.first()
    if existente is not None:
        update_fields = []
        if not existente.is_active:
            existente.is_active = True
            update_fields.append('is_active')
        # El afiliado puede proponer un codigo distinto cada vez que vuelve
        # a postularse (ver `influencer.views.suscribete`); si el cupon ya
        # existia con el codigo anterior, queda desincronizado del panel y
        # del listado de Cupones hasta que se actualiza aqui tambien.
        if existente.code != profile.referral_code:
            existente.code = profile.referral_code
            update_fields.append('code')
        if update_fields:
            existente.save(update_fields=update_fields)
        return existente

    settings_obj = InfluencerProgramSettings.load()
    return Coupon.objects.create(
        code=profile.referral_code,
        discount_type=CouponDiscountType.PERCENTAGE,
        value=settings_obj.default_customer_discount,
        influencer=profile,
        is_active=True,
    )


@transaction.atomic
def approve_influencer(profile, reviewer):
    """Aprueba (o reactiva) a un afiliado: activa su rol, genera su cupon
    personal si no existe y deja constancia de quien y cuando lo reviso."""
    profile.status = InfluencerStatus.APPROVED
    profile.is_active = True
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewer
    profile.save(update_fields=['status', 'is_active', 'reviewed_at', 'reviewed_by'])

    profile.user.es_influencer = True
    profile.user.save(update_fields=['es_influencer'])

    _ensure_personal_coupon(profile)
    return profile


def reject_influencer(profile, reviewer):
    profile.status = InfluencerStatus.REJECTED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewer
    profile.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
    return profile


def deactivate_influencer(profile):
    """Baja del programa: usada tanto por el propio afiliado (cancelar su
    suscripcion) como por un administrador. No borra nada -- conserva el
    historico de pedidos y comisiones -- solo desactiva el acceso y el
    cupon."""
    profile.is_active = False
    profile.save(update_fields=['is_active'])
    profile.coupons.update(is_active=False)
    profile.user.es_influencer = False
    profile.user.save(update_fields=['es_influencer'])
    recompute_profile_totals(profile)


@transaction.atomic
def request_withdrawal(profile):
    """Crea una solicitud de retiro por el total actualmente disponible.

    "Reserva" las comisiones aprobadas y sueltas ligandolas a la solicitud,
    para que una venta que se apruebe despues no infle un monto ya
    solicitado. Devuelve None si no hay nada disponible para retirar.
    """
    comisiones = Commission.objects.select_for_update().filter(
        influencer=profile, status=CommissionStatus.APPROVED, withdrawal_request__isnull=True,
    )
    total = comisiones.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    if total <= 0:
        return None
    solicitud = WithdrawalRequest.objects.create(influencer=profile, amount=total)
    comisiones.update(withdrawal_request=solicitud)
    recompute_profile_totals(profile)
    return solicitud


@transaction.atomic
def resolve_withdrawal(solicitud, aprobar, resolver):
    """Marca una solicitud de retiro como pagada o rechazada.

    Pagada: las comisiones ligadas pasan a `paid`. Rechazada: se sueltan
    (vuelven a estar disponibles para una futura solicitud) en vez de
    perderse.
    """
    if solicitud.status != WithdrawalStatus.PENDING:
        return solicitud

    if aprobar:
        solicitud.status = WithdrawalStatus.PAID
        solicitud.commissions.update(status=CommissionStatus.PAID)
    else:
        solicitud.status = WithdrawalStatus.REJECTED
        solicitud.commissions.update(withdrawal_request=None)

    solicitud.resolved_at = timezone.now()
    solicitud.resolved_by = resolver
    solicitud.save(update_fields=['status', 'resolved_at', 'resolved_by'])
    recompute_profile_totals(solicitud.influencer)
    return solicitud
