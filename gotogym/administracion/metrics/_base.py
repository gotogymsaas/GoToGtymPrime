"""Definiciones y ayudas compartidas por las metricas."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from orders.models import Order, OrderKind, OrderStatus, PaymentStatus

CERO = Decimal('0')

VENTA_VALIDA = Q(payment_status=PaymentStatus.APPROVED) & ~Q(
    order_status__in=(OrderStatus.CANCELLED, OrderStatus.RETURNED),
)
VENTA_ANULADA = Q(payment_status=PaymentStatus.APPROVED) & Q(
    order_status__in=(OrderStatus.CANCELLED, OrderStatus.RETURNED),
)


def _pedidos(desde, hasta, filtro=None, incluir_tarjetas=False):
    consulta = Order.objects.filter(created_at__date__gte=desde, created_at__date__lte=hasta)
    if not incluir_tarjetas:
        # Los pedidos de prueba (confirmados sin pago desde el panel) tampoco
        # son ventas; la exportacion los trae con su marca.
        consulta = consulta.exclude(kind=OrderKind.GIFT_CARD).exclude(is_test_order=True)
    return consulta.filter(filtro) if filtro is not None else consulta


def _dec(valor):
    return valor if valor is not None else CERO


def _pct(parte, total):
    """Porcentaje con un decimal, o None si no hay base."""
    if not total:
        return None
    return round(float(parte) / float(total) * 100, 1)


def periodo_anterior(desde, hasta):
    """Rango de igual duracion que termina el dia antes de `desde`."""
    dias = (hasta - desde).days + 1
    fin = desde - timedelta(days=1)
    return fin - timedelta(days=dias - 1), fin


def variacion(actual, anterior):
    """Cambio porcentual frente al periodo anterior; None si no hay base."""
    if not anterior:
        return None
    return round((float(actual) - float(anterior)) / float(anterior) * 100, 1)
