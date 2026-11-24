"""Clientes nuevos y recurrentes, canales de venta y cupones."""

from django.db.models import Count, Min, Q, Sum
from django.utils import timezone
from orders.models import Order

from ._base import CERO, VENTA_VALIDA, _dec, _pct, _pedidos

# ------------------------------------------------------ clientes y canales

def clientes(desde, hasta):
    """Nuevos frente a recurrentes entre quienes compraron en el rango.

    Nuevo = su primera venta valida de toda la historia cae dentro del rango.
    """
    validos = _pedidos(desde, hasta, VENTA_VALIDA)
    por_usuario = {
        fila['user']: fila
        for fila in validos.exclude(user=None).values('user').annotate(n=Count('id'), total=Sum('total'))
    }
    primeras = {
        fila['user']: timezone.localtime(fila['primera']).date()
        for fila in (
            Order.objects.filter(VENTA_VALIDA, user__in=list(por_usuario))
            .values('user').annotate(primera=Min('created_at'))
        )
    }
    nuevos = recurrentes = repiten = 0
    ingreso_nuevos = ingreso_recurrentes = CERO
    for usuario, fila in por_usuario.items():
        if primeras.get(usuario) and primeras[usuario] >= desde:
            nuevos += 1
            ingreso_nuevos += _dec(fila['total'])
        else:
            recurrentes += 1
            ingreso_recurrentes += _dec(fila['total'])
        if fila['n'] >= 2:
            repiten += 1
    compradores = nuevos + recurrentes
    return {
        'compradores': compradores,
        'nuevos': nuevos,
        'recurrentes': recurrentes,
        'ingreso_nuevos': ingreso_nuevos,
        'ingreso_recurrentes': ingreso_recurrentes,
        'tasa_recurrentes': _pct(recurrentes, compradores),
        'repiten_en_el_rango': repiten,
        'invitados': validos.filter(user=None).count(),
    }


def canales_de_venta(desde, hasta):
    """De donde sale el ingreso: afiliados, otros cupones o sin descuento."""
    validos = _pedidos(desde, hasta, VENTA_VALIDA)
    total = _dec(validos.aggregate(t=Sum('total'))['t'])
    grupos = [
        ('Con cupón de afiliado', Q(referred_by__isnull=False)),
        ('Con otro cupón', Q(referred_by__isnull=True) & (Q(coupon__isnull=False) | Q(discount_total__gt=0))),
        ('Sin descuento', Q(referred_by__isnull=True, coupon__isnull=True, discount_total=0)),
    ]
    filas = []
    for etiqueta, filtro in grupos:
        agregado = validos.filter(filtro).aggregate(pedidos=Count('id'), ventas=Sum('total'))
        filas.append({
            'canal': etiqueta,
            'pedidos': agregado['pedidos'] or 0,
            'ventas': _dec(agregado['ventas']),
            'participacion': _pct(_dec(agregado['ventas']), total),
        })
    return filas


def rendimiento_de_cupones(desde, hasta):
    """Por cupon: pedidos, ventas y descuento entregado. Solo cuenta pedidos
    con el cupon registrado (los anteriores a ese dato no se pueden atribuir)."""
    filas = (
        _pedidos(desde, hasta, VENTA_VALIDA)
        .filter(coupon__isnull=False)
        .values('coupon__code')
        .annotate(pedidos=Count('id'), ventas=Sum('total'), descuento=Sum('discount_total'))
        .order_by('-ventas')
    )
    return [
        {
            'codigo': fila['coupon__code'],
            'pedidos': fila['pedidos'],
            'ventas': fila['ventas'],
            'descuento': fila['descuento'],
            'descuento_sobre_ventas': _pct(fila['descuento'], fila['ventas']),
        }
        for fila in filas
    ]
