"""De lo que dice el Coach a lo que la tienda muestra y deja ejecutar.

El Coach solo propone. Aqui cada propuesta se contrasta con la base de datos
y con lo que la tienda le ofrecio en este turno, y solo sobrevive lo que la
tienda misma puede comprobar:

* Las acciones salen de una lista blanca (`contrato.ACCIONES_PERMITIDAS`) y
  se vuelven a construir con datos propios: las direcciones salen de
  `reverse()` y las etiquetas de los botones se generan aqui. De la respuesta
  del Coach no se toma ninguna URL ni ningun texto de boton.
* Un producto o una variante solo cuentan si estaban entre los candidatos del
  turno y, ademas, existen, estan activos y tienen existencias ahora.
* Las tarjetas de producto se arman con el nombre, el precio y la imagen de la
  base de datos; del Coach solo se toma el motivo, como texto.
* Una respuesta que contiene una afirmacion prohibida sobre el textil se
  rechaza entera: no se corrige ni se sustituye.

El texto que llega al navegador se pinta con `textContent`, nunca como HTML.
"""
from dataclasses import dataclass, field

from django.db.models import Prefetch
from django.urls import reverse
from django.utils.translation import gettext
from gotogym.ajustes_tienda import compras_pausadas
from inventory.services import get_available_quantity
from products.models import ProductMedia, ProductVariant
from tienda.catalog import (
    build_product_card,
    catalog_variants_queryset,
    storefront_products,
)
from tienda.templatetags.tienda_filters import cop

from . import evidencia


class RespuestaRechazada(Exception):
    """La respuesta del Coach no se puede mostrar. `codigo` es corto y no
    contiene el texto rechazado."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


@dataclass(frozen=True)
class RespuestaSegura:
    texto: str
    tarjetas: list[dict] = field(default_factory=list)
    acciones: list[dict] = field(default_factory=list)
    contacto: dict | None = None
    descartadas: int = 0


def _contiene_afirmacion_prohibida(texto, prohibidas):
    normalizado = evidencia.normalizar(texto)
    return any(termino in normalizado for termino in prohibidas)


def _ofrecido_en_el_turno(solicitud):
    """Productos y variantes que la tienda le dio al Coach en este turno."""
    productos, variantes = set(), set()
    for candidato in solicitud['evidence']['candidates']:
        productos.add(candidato['product_id'])
        variantes.update(v['id'] for v in candidato['variants'])
    return productos, variantes


def _productos_vigentes(ids):
    """`{id: producto}` de los productos que la tienda muestra hoy."""
    if not ids:
        return {}
    consulta = (
        storefront_products()
        .filter(pk__in=ids)
        .select_related('category', 'brand')
        .prefetch_related(
            Prefetch('variants', queryset=catalog_variants_queryset()),
            Prefetch('media', queryset=ProductMedia.objects.order_by('-is_primary', 'sort_order', 'id')),
        )
    )
    return {producto.id: producto for producto in consulta}


def _variantes_con_stock(ids):
    """`{id: variante}` de las variantes activas con existencias reales ahora."""
    if not ids:
        return {}
    variantes = ProductVariant.objects.filter(id__in=ids, is_active=True).select_related('product')
    return {v.id: v for v in variantes if get_available_quantity(v) > 0}


def _tarjeta(producto, razon):
    ficha = build_product_card(producto)
    imagen = ficha['image']
    precio = f"${cop(ficha['price_min'])} COP"
    return {
        'product_id': producto.id,
        'name': producto.name,
        'price': precio,
        'compare_price': f"${cop(ficha['compare_price'])} COP" if ficha['compare_price'] else '',
        'image_url': imagen.url if imagen else '',
        'url': reverse('tienda:producto_detail', args=[producto.id]),
        'reason': razon,
    }


def sanear(respuesta, solicitud):
    """`RespuestaSegura` a partir de la `RespuestaCoach` ya validada en su
    forma. Lanza `RespuestaRechazada` si no se puede mostrar."""
    prohibidas = [
        evidencia.normalizar(termino)
        for termino in solicitud['evidence']['claims_policy']['prohibited']
    ]
    textos = [respuesta.texto, *(t.razon for t in respuesta.tarjetas)]
    if any(_contiene_afirmacion_prohibida(texto, prohibidas) for texto in textos):
        raise RespuestaRechazada('afirmacion_prohibida')

    productos_ofrecidos, variantes_ofrecidas = _ofrecido_en_el_turno(solicitud)
    productos = _productos_vigentes({
        *(t.product_id for t in respuesta.tarjetas),
        *(a.product_id for a in respuesta.acciones if a.tipo == 'open_product'),
    } & productos_ofrecidos)
    variantes = _variantes_con_stock(
        {a.variant_id for a in respuesta.acciones if a.tipo == 'add_to_cart'} & variantes_ofrecidas
    )

    descartadas = respuesta.descartadas
    tarjetas = []
    for tarjeta in respuesta.tarjetas:
        producto = productos.get(tarjeta.product_id)
        if producto is None:
            descartadas += 1
            continue
        tarjetas.append(_tarjeta(producto, tarjeta.razon))

    pausadas = compras_pausadas()
    hay_carrito = solicitud['cart']['count'] > 0
    acciones = []
    vistas = set()
    for accion in respuesta.acciones:
        clave = (accion.tipo, accion.variant_id, accion.product_id)
        if clave in vistas:
            descartadas += 1
            continue
        vistas.add(clave)

        if accion.tipo == 'add_to_cart':
            variante = variantes.get(accion.variant_id)
            if variante is None or pausadas:
                descartadas += 1
                continue
            acciones.append({
                'type': 'add_to_cart',
                'variant_id': variante.id,
                'product_id': variante.product_id,
                'endpoint': reverse('carrito:add_to_cart', args=[variante.id]),
                'label': gettext('Agregar %(talla)s · %(color)s al carrito') % {
                    'talla': variante.size, 'color': variante.color,
                },
                'product_name': variante.product.name,
                'variant_label': f'{variante.size} · {variante.color}',
                'price': f'${cop(variante.effective_price)} COP',
            })
        elif accion.tipo == 'open_product':
            producto = productos.get(accion.product_id)
            if producto is None:
                descartadas += 1
                continue
            acciones.append({
                'type': 'open_product',
                'product_id': producto.id,
                'url': reverse('tienda:producto_detail', args=[producto.id]),
                'label': gettext('Ver %(nombre)s') % {'nombre': producto.name},
            })
        elif accion.tipo == 'go_checkout':
            if not hay_carrito or pausadas:
                descartadas += 1
                continue
            acciones.append({
                'type': 'go_checkout',
                'url': reverse('orders:checkout'),
                'label': gettext('Ir al pago'),
            })
        else:  # open_contact
            acciones.append({
                'type': 'open_contact',
                'url': reverse('contacto'),
                'label': gettext('Hablar con una persona'),
            })

    contacto = None
    if respuesta.handoff is not None:
        contacto = {'url': reverse('contacto'), 'label': gettext('Hablar con una persona')}
        if not any(a['type'] == 'open_contact' for a in acciones):
            acciones.append({'type': 'open_contact', **contacto})

    return RespuestaSegura(
        texto=respuesta.texto,
        tarjetas=tarjetas,
        acciones=acciones,
        contacto=contacto,
        descartadas=descartadas,
    )
