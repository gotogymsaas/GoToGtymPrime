"""Pagos de comisiones: solicitud del afiliado, resolucion por el equipo,
fechas limite e historial de lo pagado."""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone
from django.utils.formats import date_format
from gotogym.tasks import enqueue

from ..dias_habiles import enesimo_dia_habil_del_mes
from ..models import (
    Commission,
    CommissionStatus,
    ConfiguracionProgramaAfiliados,
    WithdrawalRequest,
    WithdrawalStatus,
)
from .avisos import notify_commission_paid
from .comisiones import confirmar_comisiones_vencidas, recompute_profile_totals

# El pago de las solicitudes de un mes se hace dentro de los primeros N dias
# habiles del mes siguiente.
DIAS_HABILES_PARA_PAGAR = 10


class MontoMinimoError(Exception):
    """El saldo confirmado todavia no alcanza el minimo para solicitar pago."""

    def __init__(self, minimo, disponible):
        self.minimo = minimo
        self.disponible = disponible
        super().__init__(f'El mínimo para solicitar un pago es ${minimo}; tienes ${disponible}.')


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
            raise ValueError('Los gastos de transacción deben estar entre 0 y el monto de la solicitud.')
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
