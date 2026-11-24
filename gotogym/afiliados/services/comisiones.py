"""Comisiones de los pedidos referidos: registro, validacion, confirmacion,
anulacion y los totales que ve el afiliado.

`orders` avisa de los cambios de un pedido con senales (ver `orders.senales`) y
`afiliados.receptores` las traduce a `register_order_commission`,
`schedule_order_commission_validation` y `revert_order_commission`. Esta app
solo importa los *modelos* de `orders`, nunca sus servicios.

Las funciones que avanzan el tiempo (`confirmar_comisiones_vencidas`) son
idempotentes y se invocan tambien al abrir los paneles, ademas de existir
como comando de gestion.
"""
import re
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from gotogym.tasks import enqueue
from orders.models import Order, OrderStatus, PaymentStatus

from .. import correos
from ..dias_habiles import sumar_dias_habiles
from ..models import (
    Commission,
    CommissionStatus,
    ConfiguracionProgramaAfiliados,
    WithdrawalStatus,
)

# Dias habiles tras la entrega en los que el cliente aun puede devolver.
DIAS_DE_VALIDACION = 5

# Estados de reembolso que cuentan como "reembolsado". `payments` no se puede
# importar desde aqui (son apps del mismo nivel), asi que se consulta por la
# relacion inversa del pedido: `Order.payment_transactions -> refunds`.
REEMBOLSOS_QUE_ANULAN = ('approved', 'pending')

ESTADOS_DE_PEDIDO_NO_VALIDOS = (OrderStatus.CANCELLED, OrderStatus.RETURNED)


def get_commission_rate(profile):
    if profile.commission_rate is not None:
        return profile.commission_rate
    return ConfiguracionProgramaAfiliados.load().default_commission_rate


# --- Pedidos validos y totales -------------------------------------------------

def pedido_reembolsado(order):
    return Order.objects.filter(
        pk=order.pk, payment_transactions__refunds__status__in=REEMBOLSOS_QUE_ANULAN,
    ).exists()


def pedidos_validos(profile):
    """Pedidos pagados y atribuidos al afiliado que siguen en pie: sin
    cancelar, sin devolver y sin reembolsar."""
    return (
        profile.referred_orders
        .filter(payment_status=PaymentStatus.APPROVED)
        .exclude(order_status__in=ESTADOS_DE_PEDIDO_NO_VALIDOS)
        .exclude(payment_transactions__refunds__status__in=REEMBOLSOS_QUE_ANULAN)
    )


def saldo_para_pago(profile):
    """(confirmadas, por_recuperar, neto) de lo que aun no esta ligado a una
    solicitud. Lo pendiente sigue en periodo de validacion y lo ligado ya esta
    a la espera de pago."""
    confirmadas = profile.commissions.filter(
        status=CommissionStatus.APPROVED, withdrawal_request__isnull=True,
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    por_recuperar = profile.commissions.filter(
        status=CommissionStatus.CLAWBACK, recovered_in__isnull=True,
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    return confirmadas, por_recuperar, confirmadas - por_recuperar


def recompute_profile_totals(profile):
    """Recalcula los contadores que ve el afiliado en su panel a partir de
    los pedidos y comisiones reales, en vez de confiar en que algun otro
    punto del codigo los haya incrementado a mano."""
    pedidos = pedidos_validos(profile)
    profile.total_referred = pedidos.count()
    profile.total_sales = pedidos.aggregate(total=Sum('subtotal'))['total'] or Decimal('0.00')
    profile.commission_balance = max(Decimal('0.00'), saldo_para_pago(profile)[2])
    profile.save(update_fields=['total_referred', 'total_sales', 'commission_balance'])


# --- Registro y ciclo de vida de la comision ----------------------------------

def _digitos(texto):
    return re.sub(r'\D', '', texto or '')


def _normalizado(texto):
    return ' '.join((texto or '').lower().replace(',', ' ').replace('.', ' ').split())


def razon_de_revision(order, profile):
    """Por que una compra parece una autocompra, o '' si no hay senal.

    El pedido exige sesion, asi que el caso directo (el afiliado con su propio
    codigo) ya lo bloquea `orders.services.get_usable_coupon`. Esto detecta lo
    indirecto: la misma persona con otra cuenta. No anula la comision: la
    marca para que alguien la revise."""
    razones = []
    usuario = profile.user
    if order.email and order.email.strip().lower() == (usuario.email or '').strip().lower():
        razones.append('el correo del pedido es el del afiliado')

    telefono = _digitos(order.phone)[-10:]
    telefonos = {_digitos(profile.phone)[-10:], _digitos(getattr(usuario, 'phone', ''))[-10:]} - {''}
    if len(telefono) >= 7 and telefono in telefonos:
        razones.append('el teléfono del pedido es el del afiliado')

    direccion = getattr(order, 'address', None)
    linea = _normalizado(getattr(direccion, 'address_line', ''))
    if len(linea) >= 8 and linea in _normalizado(profile.address):
        razones.append('la dirección de entrega es la del afiliado')
    return '; '.join(razones).capitalize() if razones else ''


def register_order_commission(order):
    """Crea la comision pendiente de un pedido referido cuando su pago
    queda aprobado. Idempotente: si el pedido ya tiene comision (doble
    aviso de pago) no la duplica.

    La base es el subtotal del pedido (sin envio ni impuestos), que es lo que
    dicen los terminos del programa; se guardan la base y la tasa usadas."""
    if not order.referred_by_id or Commission.objects.filter(order=order).exists():
        return None
    profile = order.referred_by
    tasa = get_commission_rate(profile)
    base = order.subtotal
    monto = (base * tasa / Decimal('100')).quantize(Decimal('0.01'))
    razon = razon_de_revision(order, profile)
    comision = Commission.objects.create(
        afiliado=profile, order=order, amount=monto, base_amount=base, rate_applied=tasa,
        needs_review=bool(razon), review_reason=razon,
    )
    recompute_profile_totals(profile)
    return comision


def fin_de_validacion(entregado_en):
    """Primer instante despues del quinto dia habil posterior a la entrega."""
    dia = sumar_dias_habiles(timezone.localtime(entregado_en).date(), DIAS_DE_VALIDACION)
    return timezone.make_aware(datetime.combine(dia + timedelta(days=1), time.min))


def schedule_order_commission_validation(order):
    """Fija cuando termina la validacion de la comision de un pedido que
    acaba de entregarse. No hace nada si el pedido no tiene comision o ya no
    esta pendiente."""
    try:
        comision = order.commission
    except Commission.DoesNotExist:
        return
    if comision.status == CommissionStatus.PENDING and order.delivered_at:
        comision.validation_ends_at = fin_de_validacion(order.delivered_at)
        comision.save(update_fields=['validation_ends_at', 'updated_at'])


@transaction.atomic
def confirmar_comisiones_vencidas(afiliado=None, ahora=None):
    """Pasa a confirmada toda comision pendiente cuya validacion termino.

    Una comision no se confirma si esta marcada para revision, si el equipo
    extendio su plazo y aun no vence, o si el pedido se cancelo, devolvio o
    reembolso (en ese caso se revierte). Devuelve cuantas confirmo."""
    ahora = ahora or timezone.now()
    pendientes = Commission.objects.filter(status=CommissionStatus.PENDING).select_related('order', 'afiliado')
    if afiliado is not None:
        pendientes = pendientes.filter(afiliado=afiliado)

    # Comisiones de pedidos ya entregados cuando no se guardaba el plazo.
    for comision in pendientes.filter(validation_ends_at__isnull=True, order__delivered_at__isnull=False):
        comision.validation_ends_at = fin_de_validacion(comision.order.delivered_at)
        comision.save(update_fields=['validation_ends_at', 'updated_at'])

    vencidas = (
        pendientes.filter(needs_review=False, validation_ends_at__lte=ahora)
        .exclude(extended_until__gt=ahora)
    )
    afectados = {}
    confirmadas = 0
    for comision in vencidas:
        if comision.order.order_status in ESTADOS_DE_PEDIDO_NO_VALIDOS or pedido_reembolsado(comision.order):
            _anular(comision, 'El pedido se canceló, devolvió o reembolso.')
        else:
            comision.status = CommissionStatus.APPROVED
            comision.save(update_fields=['status', 'updated_at'])
            confirmadas += 1
        afectados[comision.afiliado_id] = comision.afiliado
    for perfil in afectados.values():
        recompute_profile_totals(perfil)
    return confirmadas


def _anular(comision, motivo='', usuario=None):
    """Quita la comision del saldo. Si ya se pago, queda "por recuperar" y se
    descuenta del siguiente pago; si estaba en una solicitud sin pagar, se
    ajusta el monto de esa solicitud."""
    if comision.status == CommissionStatus.PAID:
        comision.status = CommissionStatus.CLAWBACK
    elif comision.status in (CommissionStatus.PENDING, CommissionStatus.APPROVED):
        solicitud = comision.withdrawal_request
        if solicitud is not None and solicitud.status == WithdrawalStatus.PENDING:
            solicitud.amount -= comision.amount
            if solicitud.amount <= 0:
                solicitud.status = WithdrawalStatus.REJECTED
                solicitud.resolved_at = timezone.now()
                solicitud.commissions.exclude(pk=comision.pk).update(withdrawal_request=None)
            solicitud.save(update_fields=['amount', 'status', 'resolved_at'])
        comision.withdrawal_request = None
        comision.status = CommissionStatus.REVERTED
    else:
        return False
    comision.adjustment_reason = motivo[:255]
    comision.adjusted_by = usuario
    comision.adjusted_at = timezone.now()
    comision.save(update_fields=[
        'status', 'withdrawal_request', 'adjustment_reason', 'adjusted_by', 'adjusted_at', 'updated_at',
    ])
    return True


def revert_order_commission(order, motivo='El pedido se canceló, devolvió o reembolso.'):
    """Revierte la comision si el pedido se cancela, se devuelve o se
    reembolsa."""
    try:
        comision = order.commission
    except Commission.DoesNotExist:
        return
    if _anular(comision, motivo):
        recompute_profile_totals(comision.afiliado)


@transaction.atomic
def anular_comision(comision, motivo, usuario):
    """Anulacion manual (fraude, error de seguimiento). Exige motivo."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ValueError('Indica el motivo de la anulación.')
    anulada = _anular(comision, motivo, usuario)
    if anulada:
        recompute_profile_totals(comision.afiliado)
    return anulada


def liberar_revision(comision, usuario, nota=''):
    """El equipo reviso la comision marcada y la deja seguir su curso."""
    comision.needs_review = False
    comision.adjustment_reason = (nota or 'Revisión resuelta.')[:255]
    comision.adjusted_by = usuario
    comision.adjusted_at = timezone.now()
    comision.save(update_fields=['needs_review', 'adjustment_reason', 'adjusted_by', 'adjusted_at', 'updated_at'])


def extender_validacion(comision, hasta, motivo, usuario):
    """Extiende el plazo de una comision pendiente hasta el final del dia
    `hasta` y avisa al afiliado."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ValueError('Indica el motivo de la extensión.')
    if comision.status != CommissionStatus.PENDING:
        raise ValueError('Solo se puede extender una comisión pendiente.')
    limite = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))
    actual = comision.confirmation_date
    if actual is not None and limite <= actual:
        raise ValueError('La nueva fecha debe ser posterior a la fecha de confirmación actual.')
    comision.extended_until = limite
    comision.extension_reason = motivo[:255]
    comision.adjusted_by = usuario
    comision.adjusted_at = timezone.now()
    comision.save(update_fields=[
        'extended_until', 'extension_reason', 'adjusted_by', 'adjusted_at', 'updated_at',
    ])
    enqueue(correos.validacion_extendida, comision.pk)
    return comision
