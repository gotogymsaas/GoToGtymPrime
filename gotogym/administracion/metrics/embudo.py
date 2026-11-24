"""Embudo de conversion, canales de trafico y busquedas."""
from collections import Counter

from analitica.models import EventoAnalitica
from products.models import Product

from ._base import VENTA_VALIDA, _pct, _pedidos

ANCHO_MOVIL = 768


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
