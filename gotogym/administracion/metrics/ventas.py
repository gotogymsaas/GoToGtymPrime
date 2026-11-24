"""Ventas: resumen, anuladas, serie diaria, meta, ranking y categorias."""
import calendar
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from orders.models import OrderItem
from payments.models import Refund

from ._base import CERO, VENTA_ANULADA, VENTA_VALIDA, _dec, _pct, _pedidos

# ---------------------------------------------------------------- ventas

def resumen_ventas(desde, hasta):
    validos = _pedidos(desde, hasta, VENTA_VALIDA)
    agregado = validos.aggregate(
        pedidos=Count('id'),
        bruto=Sum('subtotal'),
        descuentos=Sum('discount_total'),
        envio=Sum('shipping_cost'),
        cobrado=Sum('total'),
        con_tarjeta=Sum('gift_card_total'),
    )
    pedidos = agregado['pedidos'] or 0
    bruto, descuentos = _dec(agregado['bruto']), _dec(agregado['descuentos'])
    cobrado = _dec(agregado['cobrado'])
    unidades = OrderItem.objects.filter(order__in=validos).aggregate(u=Sum('quantity'))['u'] or 0
    reembolsos = _dec(
        Refund.objects
        .filter(status=Refund.Status.APPROVED, payment_transaction__order__in=validos)
        .aggregate(total=Sum('amount'))['total']
    )
    return {
        'pedidos': pedidos,
        'unidades': unidades,
        'bruto': bruto,
        'descuentos': descuentos,
        'tasa_descuento': _pct(descuentos, bruto),
        'envio': _dec(agregado['envio']),
        'cobrado': cobrado,
        'pagado_con_tarjeta_regalo': _dec(agregado['con_tarjeta']),
        'reembolsos': reembolsos,
        'neto': cobrado - reembolsos,
        'ticket_promedio': (cobrado / pedidos) if pedidos else CERO,
        'unidades_por_pedido': round(unidades / pedidos, 2) if pedidos else 0,
    }


def ventas_anuladas(desde, hasta):
    """Pedidos pagados que se cancelaron o devolvieron, y cuanto falta por
    reintegrar (los que no tienen un reembolso aprobado)."""
    anuladas = _pedidos(desde, hasta, VENTA_ANULADA)
    total = anuladas.aggregate(pedidos=Count('id'), monto=Sum('total'))
    sin_reembolso = anuladas.exclude(
        payment_transactions__refunds__status=Refund.Status.APPROVED,
    )
    por_devolver = sin_reembolso.aggregate(pedidos=Count('id'), monto=Sum('total'))
    return {
        'pedidos': total['pedidos'] or 0,
        'monto': _dec(total['monto']),
        'por_devolver_pedidos': por_devolver['pedidos'] or 0,
        'por_devolver_monto': _dec(por_devolver['monto']),
    }


def serie_diaria(desde, hasta):
    """Una fila por dia del rango, con ceros donde no hubo ventas."""
    filas = {
        fila['dia']: fila
        for fila in (
            _pedidos(desde, hasta, VENTA_VALIDA)
            .annotate(dia=TruncDate('created_at'))
            .values('dia')
            .annotate(pedidos=Count('id'), ventas=Sum('total'))
        )
    }
    serie = []
    dia = desde
    while dia <= hasta:
        fila = filas.get(dia)
        serie.append({
            'dia': dia,
            'pedidos': fila['pedidos'] if fila else 0,
            'ventas': _dec(fila['ventas']) if fila else CERO,
        })
        dia += timedelta(days=1)
    maximo = max((f['ventas'] for f in serie), default=CERO)
    for fila in serie:
        fila['relativo'] = round(float(fila['ventas']) / float(maximo) * 100) if maximo else 0
    return serie


def meta_del_mes(meta, hoy=None):
    """Avance de la meta MENSUAL, medido sobre el mes en curso.

    La meta es mensual, asi que se compara contra el mes corriente y no
    contra el rango que el usuario haya filtrado (30 dias, una semana...),
    que daba un porcentaje sin significado.
    """
    if not meta:
        return None
    hoy = hoy or timezone.localdate()
    inicio = hoy.replace(day=1)
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    ventas = resumen_ventas(inicio, hoy)
    acumulado = ventas['neto']
    transcurridos = hoy.day
    esperado = Decimal(meta) * transcurridos / dias_mes
    restantes = dias_mes - transcurridos
    return {
        'meta': Decimal(meta),
        'acumulado': acumulado,
        'avance_pct': min(100, round(float(acumulado) / float(meta) * 100)),
        'esperado_a_hoy': esperado,
        'ritmo_pct': _pct(acumulado, esperado),
        'proyeccion': acumulado / transcurridos * dias_mes,
        'diario_necesario': (Decimal(meta) - acumulado) / restantes if restantes else None,
        'dias_restantes': restantes,
        'mes_inicio': inicio,
    }


def top_productos(desde, hasta, limite=10):
    """Ranking por INGRESO (no por unidades) y agrupado por producto, no por
    SKU: con una fila por talla y color un producto con muchas variantes
    nunca llega al ranking aunque sea el que mas vende."""
    items = OrderItem.objects.filter(order__in=_pedidos(desde, hasta, VENTA_VALIDA))
    total = _dec(items.aggregate(t=Sum('line_total'))['t'])
    filas = (
        items.values('product_name_snapshot')
        .annotate(unidades=Sum('quantity'), ingresos=Sum('line_total'), pedidos=Count('order', distinct=True))
        .order_by('-ingresos', '-unidades')[:limite]
    )
    return [
        {
            'producto': fila['product_name_snapshot'],
            'unidades': fila['unidades'],
            'pedidos': fila['pedidos'],
            'ingresos': fila['ingresos'],
            'participacion': _pct(fila['ingresos'], total),
        }
        for fila in filas
    ]


def ventas_por_categoria(desde, hasta):
    items = OrderItem.objects.filter(order__in=_pedidos(desde, hasta, VENTA_VALIDA))
    total = _dec(items.aggregate(t=Sum('line_total'))['t'])
    filas = (
        items.values('variant__product__category__name')
        .annotate(unidades=Sum('quantity'), ingresos=Sum('line_total'))
        .order_by('-ingresos')
    )
    return [
        {
            'categoria': fila['variant__product__category__name'] or 'Sin categoría',
            'unidades': fila['unidades'],
            'ingresos': fila['ingresos'],
            'participacion': _pct(fila['ingresos'], total),
        }
        for fila in filas
    ]
