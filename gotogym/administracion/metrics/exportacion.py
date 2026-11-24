"""Exportacion de pedidos para analisis externo."""
from collections import defaultdict

from django.utils import timezone
from orders.models import OrderItem, OrderStatus, PaymentStatus

from ._base import _pedidos

# ------------------------------------------------------------ exportacion

def filas_exportacion(desde, hasta):
    """Pedidos del rango para analisis externo. Sin datos personales: el
    cliente es un identificador interno, no un correo ni un telefono."""
    items = defaultdict(int)
    for pedido_id, cantidad in (
        OrderItem.objects
        .filter(order__created_at__date__gte=desde, order__created_at__date__lte=hasta)
        .values_list('order_id', 'quantity')
    ):
        items[pedido_id] += cantidad
    for pedido in (
        _pedidos(desde, hasta, incluir_tarjetas=True)
        .select_related('coupon', 'referred_by__user', 'user')
        .order_by('created_at')
    ):
        yield {
            'pedido': pedido.order_number,
            'tipo': pedido.kind,
            'prueba_sin_pago': 'si' if pedido.is_test_order else 'no',
            'fecha': timezone.localtime(pedido.created_at).strftime('%Y-%m-%d %H:%M'),
            'estado_pedido': pedido.order_status,
            'estado_pago': pedido.payment_status,
            'venta_valida': 'si' if (
                not pedido.is_gift_card_purchase
                and not pedido.is_test_order
                and pedido.payment_status == PaymentStatus.APPROVED
                and pedido.order_status not in (OrderStatus.CANCELLED, OrderStatus.RETURNED)
            ) else 'no',
            'cliente_id': pedido.user_id or '',
            'unidades': items.get(pedido.pk, 0),
            'subtotal': pedido.subtotal,
            'descuento': pedido.discount_total,
            'envio': pedido.shipping_cost,
            'total': pedido.total,
            'tarjeta_regalo': pedido.gift_card_total,
            'cupon': pedido.coupon.code if pedido.coupon_id else '',
            'afiliado_id': pedido.referred_by_id or '',
        }


COLUMNAS_EXPORTACION = (
    'pedido', 'tipo', 'prueba_sin_pago', 'fecha', 'estado_pedido', 'estado_pago', 'venta_valida', 'cliente_id', 'unidades',
    'subtotal', 'descuento', 'envio', 'total', 'tarjeta_regalo', 'cupon', 'afiliado_id',
)
