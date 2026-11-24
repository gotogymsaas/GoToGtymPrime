"""Operacion e inventario: pipeline de pedidos y salud del stock."""
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from inventory.models import Inventory
from orders.models import Order, OrderItem, OrderStatus, PaymentStatus

from ._base import CERO, VENTA_VALIDA, _dec, _pct, _pedidos

DIAS_ROTACION = 30
DIAS_COBERTURA_CRITICA = 14


# ------------------------------------------------------- operacion y stock

def pipeline_de_pedidos(desde, hasta, ahora=None):
    ahora = ahora or timezone.now()
    creados = _pedidos(desde, hasta)
    total = creados.count()
    por_estado = {
        fila['order_status']: fila
        for fila in creados.values('order_status').annotate(pedidos=Count('id'), valor=Sum('total'))
    }
    etiquetas = dict(OrderStatus.choices)
    estados = [
        {
            'estado': etiquetas[estado],
            'pedidos': por_estado[estado]['pedidos'],
            'valor': _dec(por_estado[estado]['valor']),
            'participacion': _pct(por_estado[estado]['pedidos'], total),
        }
        for estado, _ in OrderStatus.choices if estado in por_estado
    ]
    sin_pagar = Order.objects.filter(
        order_status=OrderStatus.PENDING_PAYMENT, payment_status=PaymentStatus.PENDING,
        created_at__lt=ahora - timedelta(hours=24),
    ).aggregate(pedidos=Count('id'), valor=Sum('total'))
    cancelados = creados.filter(order_status=OrderStatus.CANCELLED).count()
    devueltos = creados.filter(order_status=OrderStatus.RETURNED).count()
    return {
        'creados': total,
        'estados': estados,
        'pago_rechazado': creados.filter(payment_status=PaymentStatus.REJECTED).count(),
        'tasa_cancelacion': _pct(cancelados, total),
        'tasa_devolucion': _pct(devueltos, total),
        'sin_pagar_24h': sin_pagar['pedidos'] or 0,
        'sin_pagar_24h_valor': _dec(sin_pagar['valor']),
    }


def salud_de_inventario(hoy=None, limite=10):
    """Cobertura y rotacion del inventario sobre los ultimos 30 dias.

    Un umbral fijo de "stock bajo" trata igual a una prenda que rota todos
    los dias y a una que no se mueve. Aqui se mira cuantos dias de venta
    quedan (cobertura = unidades / venta diaria) y que stock no rota.
    """
    hoy = hoy or timezone.localdate()
    desde = hoy - timedelta(days=DIAS_ROTACION - 1)
    vendidas = {
        fila['variant']: fila['u']
        for fila in (
            OrderItem.objects
            .filter(order__in=_pedidos(desde, hoy, VENTA_VALIDA), variant__isnull=False)
            .values('variant').annotate(u=Sum('quantity'))
        )
    }
    en_riesgo, sin_rotacion = [], []
    valor_total = valor_sin_rotacion = CERO
    for inv in Inventory.objects.filter(variant__is_active=True).select_related('variant__product'):
        variante = inv.variant
        cantidad = inv.quantity_available
        precio = variante.effective_price
        vendidas_30 = vendidas.get(variante.pk, 0)
        ritmo = vendidas_30 / DIAS_ROTACION
        valor_total += cantidad * precio
        if not ritmo:
            cobertura = None
        elif cantidad:
            cobertura = round(cantidad / ritmo)
        else:
            cobertura = 0
        fila = {
            'producto': variante.product.name,
            'sku': variante.sku,
            'variante': f'{variante.size}/{variante.color}',
            'disponible': cantidad,
            'vendidas_30': vendidas_30,
            'cobertura_dias': cobertura,
            'product_id': variante.product_id,
        }
        if ritmo and cantidad == 0:
            en_riesgo.append(fila)
        elif ritmo and cantidad / ritmo <= DIAS_COBERTURA_CRITICA:
            en_riesgo.append(fila)
        elif cantidad > 0 and not vendidas_30:
            fila['valor'] = cantidad * precio
            valor_sin_rotacion += fila['valor']
            sin_rotacion.append(fila)
    en_riesgo.sort(key=lambda f: (f['cobertura_dias'] or 0, -f['vendidas_30']))
    sin_rotacion.sort(key=lambda f: -f['valor'])
    return {
        'dias': DIAS_ROTACION,
        'cobertura_critica': DIAS_COBERTURA_CRITICA,
        'en_riesgo': en_riesgo[:limite],
        'en_riesgo_total': len(en_riesgo),
        'sin_rotacion': sin_rotacion[:limite],
        'sin_rotacion_total': len(sin_rotacion),
        'valor_inventario': valor_total,
        'valor_sin_rotacion': valor_sin_rotacion,
        'pct_sin_rotacion': _pct(valor_sin_rotacion, valor_total),
    }
