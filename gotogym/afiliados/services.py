"""Logica de negocio del programa de afiliados: aprobacion, comisiones,
pagos y salida del programa.

Los servicios de `orders` llaman a las funciones de comision
(`register_order_commission`, `schedule_order_commission_validation`,
`revert_order_commission`) al cambiar el estado de un pedido. Esta app solo
importa los *modelos* de `orders`, nunca sus servicios, para no formar un
ciclo.

Nada aqui depende de una tarea periodica: las funciones que avanzan el
tiempo (`confirmar_comisiones_vencidas`, `aplicar_bajas_vencidas`) son
idempotentes y se invocan tambien al abrir los paneles, ademas de existir
como comandos de gestion.
"""
import logging
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Sum
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone
from django.utils.formats import date_format
from gotogym.tasks import enqueue
from orders.models import Coupon, CouponDiscountType, Order, OrderStatus, PaymentStatus

from . import correos
from .dias_habiles import enesimo_dia_habil_del_mes, sumar_dias_habiles
from .models import (
    Commission,
    CommissionStatus,
    ConfiguracionProgramaAfiliados,
    EstadoAfiliado,
    MotivoSalida,
    PerfilAfiliado,
    WithdrawalRequest,
    WithdrawalStatus,
)
from .terminos import VERSION_TERMINOS_AFILIADOS

logger = logging.getLogger(__name__)

# Dias habiles tras la entrega en los que el cliente aun puede devolver.
DIAS_DE_VALIDACION = 5
# Dias de calendario entre el aviso de baja y su efecto.
DIAS_DE_PREAVISO = 15
# El pago de las solicitudes de un mes se hace dentro de los primeros N dias
# habiles del mes siguiente.
DIAS_HABILES_PARA_PAGAR = 10

# Estados de reembolso que cuentan como "reembolsado". `payments` no se puede
# importar desde aqui (son apps del mismo nivel), asi que se consulta por la
# relacion inversa del pedido: `Order.payment_transactions -> refunds`.
REEMBOLSOS_QUE_ANULAN = ('approved', 'pending')

ESTADOS_DE_PEDIDO_NO_VALIDOS = (OrderStatus.CANCELLED, OrderStatus.RETURNED)


class MontoMinimoError(Exception):
    """El saldo confirmado todavia no alcanza el minimo para solicitar pago."""

    def __init__(self, minimo, disponible):
        self.minimo = minimo
        self.disponible = disponible
        super().__init__(f'El minimo para solicitar un pago es ${minimo}; tienes ${disponible}.')


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
        razones.append('el telefono del pedido es el del afiliado')

    direccion = getattr(order, 'address', None)
    linea = _normalizado(getattr(direccion, 'address_line', ''))
    if len(linea) >= 8 and linea in _normalizado(profile.address):
        razones.append('la direccion de entrega es la del afiliado')
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
            _anular(comision, 'El pedido se cancelo, devolvio o reembolso.')
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


def revert_order_commission(order, motivo='El pedido se cancelo, devolvio o reembolso.'):
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
        raise ValueError('Indica el motivo de la anulacion.')
    anulada = _anular(comision, motivo, usuario)
    if anulada:
        recompute_profile_totals(comision.afiliado)
    return anulada


def liberar_revision(comision, usuario, nota=''):
    """El equipo reviso la comision marcada y la deja seguir su curso."""
    comision.needs_review = False
    comision.adjustment_reason = (nota or 'Revision resuelta.')[:255]
    comision.adjusted_by = usuario
    comision.adjusted_at = timezone.now()
    comision.save(update_fields=['needs_review', 'adjustment_reason', 'adjusted_by', 'adjusted_at', 'updated_at'])


def extender_validacion(comision, hasta, motivo, usuario):
    """Extiende el plazo de una comision pendiente hasta el final del dia
    `hasta` y avisa al afiliado."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ValueError('Indica el motivo de la extension.')
    if comision.status != CommissionStatus.PENDING:
        raise ValueError('Solo se puede extender una comision pendiente.')
    limite = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))
    actual = comision.confirmation_date
    if actual is not None and limite <= actual:
        raise ValueError('La nueva fecha debe ser posterior a la fecha de confirmacion actual.')
    comision.extended_until = limite
    comision.extension_reason = motivo[:255]
    comision.adjusted_by = usuario
    comision.adjusted_at = timezone.now()
    comision.save(update_fields=[
        'extended_until', 'extension_reason', 'adjusted_by', 'adjusted_at', 'updated_at',
    ])
    enqueue(correos.validacion_extendida, comision.pk)
    return comision


# --- Aprobacion, rechazo y salida ----------------------------------------------

def _ensure_personal_coupon(profile):
    """Genera (o reactiva) el cupon personal del afiliado: el mismo codigo
    que ve en su panel (`referral_code`) queda utilizable en el checkout."""
    existente = profile.coupons.first()
    if existente is not None:
        update_fields = []
        if not existente.is_active:
            existente.is_active = True
            update_fields.append('is_active')
        # El afiliado puede proponer un codigo distinto cada vez que vuelve
        # a postularse (ver `afiliados.views.suscribete`); si el cupon ya
        # existia con el codigo anterior, queda desincronizado del panel y
        # del listado de Cupones hasta que se actualiza aqui tambien.
        if existente.code != profile.referral_code:
            existente.code = profile.referral_code
            update_fields.append('code')
        if update_fields:
            existente.save(update_fields=update_fields)
        return existente

    settings_obj = ConfiguracionProgramaAfiliados.load()
    return Coupon.objects.create(
        code=profile.referral_code,
        discount_type=CouponDiscountType.PERCENTAGE,
        value=settings_obj.default_customer_discount,
        afiliado=profile,
        is_active=True,
    )


def _limpiar_salida(profile):
    profile.exit_requested_at = None
    profile.exit_effective_at = None
    profile.exited_at = None
    profile.exit_reason = ''
    profile.exit_notes = ''


@transaction.atomic
def approve_afiliado(profile, reviewer):
    """Aprueba (o reactiva) a un afiliado: activa su rol, genera su cupon
    personal si no existe y deja constancia de quien y cuando lo reviso."""
    profile.status = EstadoAfiliado.APPROVED
    profile.is_active = True
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewer
    profile.rejection_reason = ''
    _limpiar_salida(profile)
    profile.save(update_fields=[
        'status', 'is_active', 'reviewed_at', 'reviewed_by', 'rejection_reason',
        'exit_requested_at', 'exit_effective_at', 'exited_at', 'exit_reason', 'exit_notes',
    ])

    profile.user.es_afiliado = True
    profile.user.save(update_fields=['es_afiliado'])

    _ensure_personal_coupon(profile)
    enqueue(correos.afiliado_aprobado, profile.pk)
    return profile


def reject_afiliado(profile, reviewer, motivo=''):
    profile.status = EstadoAfiliado.REJECTED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewer
    profile.rejection_reason = (motivo or '').strip()[:500]
    profile.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'rejection_reason'])
    enqueue(correos.afiliado_rechazado, profile.pk)
    return profile


def deactivate_afiliado(profile, motivo='', notas='', anular_comisiones=False, usuario=None):
    """Baja del programa: usada por el afiliado al cancelar su solicitud, por
    el vencimiento de su preaviso y por un administrador. No borra nada --
    conserva el historico de pedidos y comisiones -- solo desactiva el acceso
    y el cupon. Las comisiones que ya tiene siguen su curso y se le pagan.

    `motivo` es un `MotivoSalida`. Sin motivo, una baja con preaviso queda
    como voluntaria. Si se da de baja a quien aun era aprobado, se le avisa.
    `anular_comisiones` invalida las que aun no se han pagado (fraude)."""
    era_aprobado = profile.status == EstadoAfiliado.APPROVED and profile.is_active
    if not motivo and profile.exit_requested_at:
        motivo = MotivoSalida.VOLUNTARY
    profile.is_active = False
    profile.exited_at = timezone.now()
    profile.exit_reason = motivo
    profile.exit_notes = (notas or '').strip()
    profile.save(update_fields=['is_active', 'exited_at', 'exit_reason', 'exit_notes'])
    profile.coupons.update(is_active=False)
    profile.user.es_afiliado = False
    profile.user.save(update_fields=['es_afiliado'])

    if anular_comisiones:
        texto = f'Anulada por la terminacion del afiliado: {profile.exit_notes or profile.get_exit_reason_display()}'
        for comision in profile.commissions.filter(
            status__in=(CommissionStatus.PENDING, CommissionStatus.APPROVED),
        ).select_related('withdrawal_request'):
            _anular(comision, texto, usuario)
    recompute_profile_totals(profile)

    if era_aprobado:
        if motivo == MotivoSalida.VOLUNTARY:
            enqueue(correos.baja_efectiva, profile.pk)
        elif motivo:
            enqueue(correos.terminacion, profile.pk)


def solicitar_baja(profile, ahora=None):
    """Registra el aviso de baja del afiliado: se hace efectiva tras el
    preaviso y, mientras tanto, su codigo y su panel siguen activos."""
    if not profile.is_active or profile.exit_requested_at:
        return profile
    ahora = ahora or timezone.now()
    profile.exit_requested_at = ahora
    profile.exit_effective_at = ahora + timedelta(days=DIAS_DE_PREAVISO)
    profile.save(update_fields=['exit_requested_at', 'exit_effective_at'])
    enqueue(correos.baja_solicitada, profile.pk)
    return profile


def cancelar_baja(profile):
    profile.exit_requested_at = None
    profile.exit_effective_at = None
    profile.save(update_fields=['exit_requested_at', 'exit_effective_at'])
    return profile


def aplicar_bajas_vencidas(ahora=None):
    """Da de baja a quien ya cumplio su preaviso. Devuelve cuantos."""
    ahora = ahora or timezone.now()
    vencidos = list(PerfilAfiliado.objects.filter(is_active=True, exit_effective_at__lte=ahora))
    for perfil in vencidos:
        deactivate_afiliado(perfil, motivo=MotivoSalida.VOLUNTARY)
    return len(vencidos)


def afiliado_operativo(profile, ahora=None):
    """Si el codigo del afiliado todavia debe aceptarse: esta activo y su
    preaviso de baja, si lo hay, no ha vencido (aunque la baja aun no se haya
    aplicado en la base)."""
    ahora = ahora or timezone.now()
    if not profile.is_active:
        return False
    return not (profile.exit_effective_at and profile.exit_effective_at <= ahora)


def necesita_reaceptar_terminos(profile):
    """Los afiliados activos deben haber aceptado la version vigente."""
    return (
        profile.status == EstadoAfiliado.APPROVED
        and profile.is_active
        and profile.terms_version != VERSION_TERMINOS_AFILIADOS
    )


def aceptar_terminos_vigentes(profile):
    profile.terms_version = VERSION_TERMINOS_AFILIADOS
    profile.terms_accepted_at = timezone.now()
    profile.save(update_fields=['terms_version', 'terms_accepted_at'])


# --- Actividad ----------------------------------------------------------------

def ultima_actividad(profile):
    """Ultimo clic o ultima venta del afiliado; si no tiene ninguno, cuando
    fue aprobado o se postulo."""
    ultimo_clic = profile.referral_clicks.aggregate(m=Max('created_at'))['m']
    ultima_venta = profile.referred_orders.aggregate(m=Max('created_at'))['m']
    fechas = [f for f in (ultimo_clic, ultima_venta) if f]
    return max(fechas) if fechas else (profile.reviewed_at or profile.created_at)


def afiliados_inactivos(dias=None, ahora=None):
    """Afiliados activos sin clics ni ventas hace `dias` dias o mas, con su
    ultima actividad. No se da de baja a nadie automaticamente."""
    ahora = ahora or timezone.now()
    dias = dias if dias is not None else ConfiguracionProgramaAfiliados.load().inactivity_days
    limite = ahora - timedelta(days=dias)
    perfiles = (
        PerfilAfiliado.objects.filter(status=EstadoAfiliado.APPROVED, is_active=True)
        .select_related('user')
    )
    resultado = []
    for perfil in perfiles:
        ultima = ultima_actividad(perfil)
        if ultima < limite:
            resultado.append((perfil, ultima))
    return resultado


# --- Pagos --------------------------------------------------------------------

def fecha_limite_de_pago(fecha_solicitud):
    """Dentro de los primeros 10 dias habiles del mes siguiente al de la
    solicitud."""
    anio, mes = (fecha_solicitud.year + 1, 1) if fecha_solicitud.month == 12 else (
        fecha_solicitud.year, fecha_solicitud.month + 1,
    )
    return enesimo_dia_habil_del_mes(anio, mes, DIAS_HABILES_PARA_PAGAR)


def fecha_limite_de_la_solicitud(solicitud):
    return fecha_limite_de_pago(timezone.localtime(solicitud.requested_at).date())


@transaction.atomic
def request_withdrawal(profile, payment_details=''):
    """Crea una solicitud de pago por el total de comisiones confirmadas
    disponible, menos lo que se debe recuperar de pedidos devueltos.

    `payment_details` es lo que el afiliado escribio: datos de la cuenta y
    nota para el pago.

    "Reserva" las comisiones confirmadas (y las por recuperar) ligandolas a
    la solicitud, para que una venta que se confirme despues no infle un
    monto ya solicitado. Devuelve None si no hay nada disponible; lanza
    `MontoMinimoError` si lo disponible no llega al minimo.
    """
    confirmar_comisiones_vencidas(afiliado=profile)
    propias = Commission.objects.select_for_update().filter(afiliado=profile)
    confirmadas = propias.filter(status=CommissionStatus.APPROVED, withdrawal_request__isnull=True)
    por_recuperar = propias.filter(status=CommissionStatus.CLAWBACK, recovered_in__isnull=True)
    total = confirmadas.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    recuperar = por_recuperar.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    neto = total - recuperar
    if neto <= 0:
        return None
    minimo = ConfiguracionProgramaAfiliados.load().minimum_payout
    if neto < minimo:
        raise MontoMinimoError(minimo, neto)
    solicitud = WithdrawalRequest.objects.create(
        afiliado=profile, amount=neto, recovery_amount=recuperar, payment_details=payment_details,
    )
    confirmadas.update(withdrawal_request=solicitud)
    por_recuperar.update(recovered_in=solicitud)
    recompute_profile_totals(profile)
    return solicitud


@transaction.atomic
def resolve_withdrawal(solicitud, aprobar, resolver, transaction_fee=Decimal('0.00')):
    """Marca una solicitud de pago como pagada o rechazada.

    Pagada: las comisiones ligadas pasan a `paid` y lo recuperado queda
    saldado; `transaction_fee` son los gastos de transaccion, que descuenta el
    pago. Rechazada: se sueltan (vuelven a estar disponibles para una futura
    solicitud) en vez de perderse.
    """
    if solicitud.status != WithdrawalStatus.PENDING:
        return solicitud

    if aprobar:
        transaction_fee = Decimal(transaction_fee or 0).quantize(Decimal('0.01'))
        if transaction_fee < 0 or transaction_fee > solicitud.amount:
            raise ValueError('Los gastos de transaccion deben estar entre 0 y el monto de la solicitud.')
        solicitud.status = WithdrawalStatus.PAID
        solicitud.transaction_fee = transaction_fee
        solicitud.commissions.filter(status=CommissionStatus.APPROVED).update(status=CommissionStatus.PAID)
        solicitud.recovered_commissions.update(status=CommissionStatus.REVERTED)
    else:
        solicitud.status = WithdrawalStatus.REJECTED
        solicitud.commissions.update(withdrawal_request=None)
        solicitud.recovered_commissions.update(recovered_in=None)

    solicitud.resolved_at = timezone.now()
    solicitud.resolved_by = resolver
    solicitud.save(update_fields=['status', 'resolved_at', 'resolved_by', 'transaction_fee'])
    recompute_profile_totals(solicitud.afiliado)
    if aprobar:
        # Se encola despues de confirmar la transaccion: si algo la revierte,
        # el afiliado no recibe un aviso de un pago que no quedo registrado.
        # Se pasa el id (no el objeto) para que la tarea pueda viajar por una
        # cola de verdad.
        enqueue(notify_commission_paid, solicitud.pk)
    return solicitud


def _total_pagado(solicitudes):
    neto = ExpressionWrapper(F('amount') - F('transaction_fee'), output_field=DecimalField(max_digits=12, decimal_places=2))
    return solicitudes.aggregate(total=Sum(neto))['total'] or Decimal('0.00')


def total_pagado_en_anio(afiliado, anio):
    """Total que se le ha pagado al afiliado en un ano calendario (zona
    America/Bogota), neto de gastos de transaccion. No incluye retenciones:
    el programa no las aplica."""
    return _total_pagado(WithdrawalRequest.objects.filter(
        afiliado=afiliado, status=WithdrawalStatus.PAID, resolved_at__year=anio,
    ))


def totales_pagados_por_anio(afiliado):
    """[(anio, total, cantidad de pagos)] del mas reciente al mas antiguo."""
    neto = ExpressionWrapper(F('amount') - F('transaction_fee'), output_field=DecimalField(max_digits=12, decimal_places=2))
    filas = (
        WithdrawalRequest.objects.filter(afiliado=afiliado, status=WithdrawalStatus.PAID)
        .annotate(anio=TruncYear('resolved_at'))
        .values('anio')
        .annotate(total=Sum(neto), cantidad=Count('pk'))
        .order_by('-anio')
    )
    return [(fila['anio'].year, fila['total'], fila['cantidad']) for fila in filas]


def pagos_por_mes(afiliado, anio):
    """Los doce meses de `anio` con lo pagado en cada uno (por fecha de pago,
    zona America/Bogota). Los meses sin pagos salen en cero para que el
    historial se lea completo: cantidad, monto solicitado, gastos y lo que
    efectivamente recibio."""
    filas = (
        WithdrawalRequest.objects.filter(afiliado=afiliado, status=WithdrawalStatus.PAID, resolved_at__year=anio)
        .annotate(mes=TruncMonth('resolved_at'))
        .values('mes')
        .annotate(bruto=Sum('amount'), gastos=Sum('transaction_fee'), cantidad=Count('pk'))
    )
    por_mes = {fila['mes'].month: fila for fila in filas}
    meses = []
    for numero in range(1, 13):
        fila = por_mes.get(numero)
        bruto = fila['bruto'] if fila else Decimal('0.00')
        gastos = fila['gastos'] if fila else Decimal('0.00')
        meses.append({
            'mes': date(anio, numero, 1), 'cantidad': fila['cantidad'] if fila else 0,
            'bruto': bruto, 'gastos': gastos, 'neto': bruto - gastos,
        })
    return meses


def historial_de_pagos(afiliado, anio=None, mes=None):
    """Todo lo que las pantallas de pagos (la del afiliado y la del equipo)
    muestran: totales por ano, el desglose por mes del ano elegido, los pagos
    de ese ano (o solo del mes elegido) y las solicitudes que siguen en curso.

    Los anos del desplegable cubren desde el primero con actividad (alta del
    afiliado o primer pago) hasta el actual, sin saltos, para poder consultar
    tambien un ano en el que no hubo pagos."""
    hoy = timezone.localdate()
    anio = anio or hoy.year
    anios = totales_pagados_por_anio(afiliado)
    anios_con_pagos = {a for a, _, _ in anios}
    primero = min(anios_con_pagos | {timezone.localtime(afiliado.created_at).year, anio})
    anios_visibles = sorted(set(range(primero, hoy.year + 1)) | anios_con_pagos | {anio}, reverse=True)
    meses = pagos_por_mes(afiliado, anio)
    fila_mes = meses[mes - 1] if mes else None
    pagos = WithdrawalRequest.objects.filter(
        afiliado=afiliado, status=WithdrawalStatus.PAID, resolved_at__year=anio,
    )
    if mes:
        pagos = pagos.filter(resolved_at__month=mes)
    return {
        'anio': anio,
        'mes': mes,
        'fila_mes': fila_mes,
        'periodo': date_format(fila_mes['mes'], r'F \d\e Y').lower() if fila_mes else str(anio),
        'meses_a_mostrar': [fila_mes] if fila_mes else meses,
        'anios': anios_visibles,
        'totales_por_anio': anios,
        'total_historico': sum((total for _, total, _ in anios), Decimal('0.00')),
        'meses': meses,
        'total_del_anio': sum((m['neto'] for m in meses), Decimal('0.00')),
        'cantidad_del_anio': sum(m['cantidad'] for m in meses),
        'bruto_del_anio': sum((m['bruto'] for m in meses), Decimal('0.00')),
        'gastos_del_anio': sum((m['gastos'] for m in meses), Decimal('0.00')),
        'pagos': pagos.order_by('-resolved_at'),
        'solicitudes_en_curso': WithdrawalRequest.objects.filter(
            afiliado=afiliado, status=WithdrawalStatus.PENDING,
        ).order_by('-requested_at'),
    }


def anio_pedido(valor, por_defecto=None):
    """El ano del filtro `?anio=`, o el actual si falta o es invalido."""
    por_defecto = por_defecto or timezone.localdate().year
    try:
        anio = int(valor)
    except (TypeError, ValueError):
        return por_defecto
    return anio if 2000 <= anio <= por_defecto + 1 else por_defecto


def mes_pedido(valor):
    """El mes (1-12) del filtro `?mes=`, o None (todo el ano) si falta o es invalido."""
    try:
        mes = int(valor)
    except (TypeError, ValueError):
        return None
    return mes if 1 <= mes <= 12 else None


def notify_commission_paid(solicitud_id):
    """Avisa por correo al afiliado que su solicitud de comision fue pagada,
    con el desglose de lo que recibe.

    Un fallo de correo nunca debe deshacer ni ocultar el pago ya registrado:
    se deja en el log y el administrador sigue su flujo.
    """
    from tienda.templatetags.tienda_filters import cop

    solicitud = WithdrawalRequest.objects.select_related('afiliado__user').get(pk=solicitud_id)
    usuario = solicitud.afiliado.user
    nombre = usuario.first_name or usuario.email
    desglose = ''
    if solicitud.recovery_amount or solicitud.transaction_fee:
        lineas = []
        if solicitud.recovery_amount:
            lineas.append(f'Descontado por pedidos devueltos o reembolsados: ${cop(solicitud.recovery_amount)} COP (ya incluido en el monto).')
        if solicitud.transaction_fee:
            lineas.append(f'Gastos de transaccion: ${cop(solicitud.transaction_fee)} COP.')
        lineas.append(f'Total recibido: ${cop(solicitud.net_paid)} COP.')
        desglose = '\n'.join(lineas) + '\n\n'
    cuerpo = (
        f'Hola {nombre},\n\n'
        f'Te confirmamos que pagamos tu solicitud de comision por ${cop(solicitud.amount)} COP, '
        f'solicitada el {timezone.localtime(solicitud.requested_at):%d/%m/%Y}.\n\n'
        f'{desglose}'
        'Si tienes alguna duda sobre el pago, escribenos a support@gotogym.store.\n\n'
        'Gracias por hacer parte del programa de afiliados de GoToGym.\n'
        'Equipo GoToGym\n'
    )
    try:
        send_mail(
            subject='Tu comision de GoToGym fue pagada',
            message=cuerpo,
            from_email=None,
            recipient_list=[usuario.email],
        )
    except Exception:
        logger.exception('No se pudo enviar el aviso de pago de comision (solicitud %s)', solicitud.pk)


# --- Avisos a los afiliados ---------------------------------------------------

def perfiles_activos():
    return PerfilAfiliado.objects.filter(status=EstadoAfiliado.APPROVED, is_active=True)


def avisar_afiliados(asunto, mensaje):
    """Envia un aviso a todos los afiliados activos (cambio de terminos,
    del programa, etc.). Devuelve a cuantos."""
    ids = list(perfiles_activos().values_list('pk', flat=True))
    for perfil_id in ids:
        enqueue(correos.aviso_general, perfil_id, asunto, mensaje)
    return len(ids)


def avisar_cambio_de_tasa(nueva_tasa, afiliado=None):
    """Avisa de un cambio de comision: a un afiliado si tiene tasa propia, o
    a todos los que usan la tasa global. Aplica a ventas posteriores."""
    if afiliado is not None:
        destinatarios = [afiliado.pk]
    else:
        destinatarios = list(perfiles_activos().filter(commission_rate__isnull=True).values_list('pk', flat=True))
    for perfil_id in destinatarios:
        enqueue(correos.cambio_de_tasa, perfil_id, str(nueva_tasa))
    return len(destinatarios)
