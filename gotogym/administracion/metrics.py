"""Metricas de negocio del panel: definiciones, no pantallas.

Cada funcion devuelve datos planos para que las vistas y las pruebas
dependan de la *definicion* de la metrica y no de como se dibuja.

Definiciones que importan (y por que estan escritas aqui)
---------------------------------------------------------

**Venta valida** = pago aprobado y pedido que no esta cancelado ni devuelto.
`payment_status` no cambia cuando un pedido se cancela, se devuelve o se
reembolsa (lo controla solo el proveedor de pago), asi que filtrar solo por
"pago aprobado" cuenta como ingreso dinero que en realidad ya se reintegro o
se debe reintegrar. Esos pedidos se muestran aparte como *ventas anuladas*,
con lo que falta por devolver, que es lo accionable.

**Ingreso neto** = total cobrado de las ventas validas menos los reembolsos
aprobados sobre ellas (devoluciones parciales).

**Ticket promedio** = total cobrado / pedidos validos (incluye envio, porque
es lo que paga el cliente en cada compra).

**Periodo anterior** = el mismo numero de dias inmediatamente antes del rango
elegido. Un numero sin termino de comparacion no dice si el negocio va bien.

**Fecha de una venta** = la de creacion del pedido. No hay fecha de
aprobacion del pago guardada en el pedido; con pagos de aprobacion diferida
una venta puede caer en un dia anterior al de su cobro.

**Embudo** = sesiones (visitantes estables, ver `analitica.services`) que
alcanzaron cada etapa, donde cada etapa exige haber pasado la anterior. Mide
solo a quien acepta ser medido: quedan fuera las personas con Do Not Track
y las que usan bloqueadores, asi que las cifras absolutas son un piso y lo
util son las proporciones entre etapas.
"""
import calendar
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from analitica.models import EventoAnalitica
from django.db.models import Count, Min, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from inventory.models import Inventory
from orders.models import Order, OrderItem, OrderStatus, PaymentStatus
from payments.models import Refund
from products.models import Product

CERO = Decimal('0')
ANCHO_MOVIL = 768
DIAS_ROTACION = 30
DIAS_COBERTURA_CRITICA = 14

VENTA_VALIDA = Q(payment_status=PaymentStatus.APPROVED) & ~Q(
    order_status__in=(OrderStatus.CANCELLED, OrderStatus.RETURNED),
)
VENTA_ANULADA = Q(payment_status=PaymentStatus.APPROVED) & Q(
    order_status__in=(OrderStatus.CANCELLED, OrderStatus.RETURNED),
)


def _pedidos(desde, hasta, filtro=None):
    consulta = Order.objects.filter(created_at__date__gte=desde, created_at__date__lte=hasta)
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


# ---------------------------------------------------------------- ventas

def resumen_ventas(desde, hasta):
    validos = _pedidos(desde, hasta, VENTA_VALIDA)
    agregado = validos.aggregate(
        pedidos=Count('id'),
        bruto=Sum('subtotal'),
        descuentos=Sum('discount_total'),
        envio=Sum('shipping_cost'),
        cobrado=Sum('total'),
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
            'categoria': fila['variant__product__category__name'] or 'Sin categoria',
            'unidades': fila['unidades'],
            'ingresos': fila['ingresos'],
            'participacion': _pct(fila['ingresos'], total),
        }
        for fila in filas
    ]


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
        ('Con cupon de afiliado', Q(referred_by__isnull=False)),
        ('Con otro cupon', Q(referred_by__isnull=True) & (Q(coupon__isnull=False) | Q(discount_total__gt=0))),
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


# ----------------------------------------------------------------- embudo

ETAPAS = (
    ('sesiones', 'Sesiones'),
    ('producto', 'Vieron un producto'),
    ('carrito', 'Agregaron al carrito'),
    ('checkout', 'Llegaron al checkout'),
    ('pedido', 'Crearon un pedido'),
)


def _sesiones(eventos, **filtros):
    return set(eventos.filter(**filtros).values_list('sesion', flat=True).distinct()) - {''}


def _etapas(eventos):
    """Conjuntos de sesiones por etapa, cada uno contenido en el anterior."""
    vistas = eventos.filter(nombre='page_view')
    conjuntos = [
        set(vistas.values_list('sesion', flat=True).distinct()) - {''},
        _sesiones(vistas, ruta__contains='/tienda/producto/'),
        _sesiones(eventos, nombre='add_to_cart'),
        _sesiones(vistas, ruta__contains='/pedidos-tienda/checkout'),
        _sesiones(eventos, nombre='order_created'),
    ]
    acumulado = conjuntos[0]
    for indice in range(1, len(conjuntos)):
        acumulado = acumulado & conjuntos[indice]
        conjuntos[indice] = acumulado
    return conjuntos


def _filas_embudo(conjuntos):
    filas = []
    base = len(conjuntos[0])
    anterior = base
    for (clave, nombre), conjunto in zip(ETAPAS, conjuntos, strict=True):
        cantidad = len(conjunto)
        filas.append({
            'clave': clave,
            'etapa': nombre,
            'sesiones': cantidad,
            'del_inicio': _pct(cantidad, base),
            'del_paso_anterior': _pct(cantidad, anterior) if clave != 'sesiones' else None,
            'ancho': round(cantidad / base * 100) if base else 0,
        })
        anterior = cantidad
    return filas


def _dispositivo_por_sesion(eventos):
    """'movil' o 'escritorio' segun el ancho de la primera vista de la sesion."""
    dispositivos = {}
    filas = (
        eventos.filter(nombre='page_view')
        .order_by('creado')
        .values_list('sesion', 'propiedades__ancho')
    )
    for sesion, ancho in filas:
        if not sesion or sesion in dispositivos:
            continue
        if isinstance(ancho, (int, float)):
            dispositivos[sesion] = 'movil' if ancho < ANCHO_MOVIL else 'escritorio'
        else:
            dispositivos[sesion] = 'sin dato'
    return dispositivos


def embudo(desde, hasta):
    eventos = EventoAnalitica.objects.filter(creado__date__gte=desde, creado__date__lte=hasta)
    conjuntos = _etapas(eventos)
    dispositivo = _dispositivo_por_sesion(eventos)

    por_dispositivo = {}
    for nombre in ('movil', 'escritorio'):
        propios = [{s for s in conjunto if dispositivo.get(s) == nombre} for conjunto in conjuntos]
        por_dispositivo[nombre] = _filas_embudo(propios)

    comparativo = [
        {'etapa': movil['etapa'], 'movil': movil, 'escritorio': escritorio}
        for movil, escritorio in zip(
            por_dispositivo['movil'], por_dispositivo['escritorio'], strict=True,
        )
    ]
    pedidos_pagados = _pedidos(desde, hasta, VENTA_VALIDA).count()
    sesiones = len(conjuntos[0])
    return {
        'etapas': _filas_embudo(conjuntos),
        'por_dispositivo': por_dispositivo,
        'comparativo_dispositivos': comparativo,
        'pedidos_pagados': pedidos_pagados,
        'conversion_pagada': _pct(pedidos_pagados, sesiones),
        'hay_datos': sesiones > 0,
    }


def _canal_de(propiedades):
    fuente = propiedades.get('utm_source')
    if fuente:
        medio = propiedades.get('utm_medium')
        return f'{fuente} / {medio}' if medio else str(fuente)
    if propiedades.get('ref'):
        return f"Afiliado: {propiedades['ref']}"
    if propiedades.get('referrer'):
        return str(propiedades['referrer'])
    return None


def canales_de_trafico(desde, hasta, limite=10):
    """Sesiones, carritos y pedidos por canal de entrada.

    El canal se toma de la primera vista de la sesion (utm, codigo de
    afiliado o sitio de origen). Una sesion sin ninguno de esos datos se
    agrupa como "Directo / sin dato": incluye visitas directas, apps que no
    envian origen y dispositivos que ocultan el referente.
    """
    eventos = EventoAnalitica.objects.filter(creado__date__gte=desde, creado__date__lte=hasta)
    conjuntos = _etapas(eventos)
    canal_por_sesion = {}
    for sesion, propiedades in (
        eventos.filter(nombre='page_view').order_by('creado').values_list('sesion', 'propiedades')
    ):
        # Se conserva el primer origen conocido de la sesion: la primera
        # vista puede no traerlo y una posterior si.
        if sesion and canal_por_sesion.get(sesion) is None:
            canal_por_sesion[sesion] = _canal_de(propiedades or {})

    sesiones, carritos, pedidos = Counter(), Counter(), Counter()
    for sesion in conjuntos[0]:
        canal = canal_por_sesion.get(sesion) or 'Directo / sin dato'
        sesiones[canal] += 1
        if sesion in conjuntos[2]:
            carritos[canal] += 1
        if sesion in conjuntos[4]:
            pedidos[canal] += 1
    return [
        {
            'canal': canal,
            'sesiones': cantidad,
            'carritos': carritos[canal],
            'pedidos': pedidos[canal],
            'conversion': _pct(pedidos[canal], cantidad),
        }
        for canal, cantidad in sesiones.most_common(limite)
    ]


def busquedas(desde, hasta, limite=15):
    """Terminos mas buscados y cuales no devuelven nada en el catalogo.

    Una busqueda sin resultados es demanda que la tienda no esta atendiendo:
    se mira contra el mismo criterio de la tienda (nombre contiene el
    termino)."""
    eventos = EventoAnalitica.objects.filter(
        nombre='search_submit', creado__date__gte=desde, creado__date__lte=hasta,
    )
    conteo = Counter()
    sin_termino = 0
    for propiedades in eventos.values_list('propiedades', flat=True):
        termino = str((propiedades or {}).get('termino', '')).strip().lower()
        if termino:
            conteo[termino] += 1
        else:
            sin_termino += 1
    filas = []
    for termino, veces in conteo.most_common(limite):
        resultados = Product.objects.filter(name__icontains=termino).count()
        filas.append({'termino': termino, 'veces': veces, 'resultados': resultados})
    return {
        'total': sum(conteo.values()) + sin_termino,
        'sin_termino': sin_termino,
        'terminos': filas,
        'sin_resultados': [fila for fila in filas if fila['resultados'] == 0],
    }


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
        _pedidos(desde, hasta)
        .select_related('coupon', 'referred_by__user', 'user')
        .order_by('created_at')
    ):
        yield {
            'pedido': pedido.order_number,
            'fecha': timezone.localtime(pedido.created_at).strftime('%Y-%m-%d %H:%M'),
            'estado_pedido': pedido.order_status,
            'estado_pago': pedido.payment_status,
            'venta_valida': 'si' if (
                pedido.payment_status == PaymentStatus.APPROVED
                and pedido.order_status not in (OrderStatus.CANCELLED, OrderStatus.RETURNED)
            ) else 'no',
            'cliente_id': pedido.user_id or '',
            'unidades': items.get(pedido.pk, 0),
            'subtotal': pedido.subtotal,
            'descuento': pedido.discount_total,
            'envio': pedido.shipping_cost,
            'total': pedido.total,
            'cupon': pedido.coupon.code if pedido.coupon_id else '',
            'afiliado_id': pedido.referred_by_id or '',
        }


COLUMNAS_EXPORTACION = (
    'pedido', 'fecha', 'estado_pedido', 'estado_pago', 'venta_valida', 'cliente_id', 'unidades',
    'subtotal', 'descuento', 'envio', 'total', 'cupon', 'afiliado_id',
)
