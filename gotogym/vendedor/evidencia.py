"""Evidencia que la tienda entrega al Coach en cada turno.

La tienda es la unica fuente de verdad de precio, existencias y politicas: el
Coach razona y redacta con lo que se le entrega aqui, no con lo que "sabe".

**Candidatos.** Productos con existencias reales, elegidos sin consultar al
modelo y sin adivinar intenciones: primero el producto de la pagina que mira
el visitante, luego los de su carrito, luego los que comparten palabras con su
mensaje y, si sobra espacio, el resto del catalogo en el orden del panel. Es
recuperacion de candidatos, no clasificacion de lo que quiere el visitante;
quien decide que recomendar es el Coach.

**Politicas.** Se entregan con su version y su estado de revision. Una politica
pendiente de revision juridica no viaja con su texto, solo con un aviso, para
que el agente no repita un plazo que la tienda aun no ha validado.

Los textos de descripcion son datos del catalogo escritos por personas: el
Coach los trata como datos, nunca como instrucciones.
"""
import hashlib
import re
import unicodedata
from decimal import Decimal

from django.conf import settings
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone
from gotogym.afirmaciones import PROHIBIDAS
from orders.models import Coupon
from tienda.catalog import (
    ORDEN_DEL_PANEL,
    catalog_variants_queryset,
    size_sort_key,
    storefront_products,
    variant_stock,
)

from gotogym import politicas_contenido as politicas_es
from gotogym import politicas_contenido_en as politicas_en

from . import contrato

# Techo de productos que se leen del catalogo para elegir candidatos. El
# catalogo actual tiene decenas de productos; el tope evita que uno enorme
# convierta cada mensaje en una lectura completa.
MAX_PRODUCTOS_LEIDOS = 200

# (clave que viaja, constante en politicas_contenido, clave de revision)
POLITICAS = (
    ('cambios', 'CAMBIOS'),
    ('devoluciones', 'DEVOLUCIONES'),
    ('garantia', 'GARANTIA'),
    ('envios', 'ENVIOS'),
    ('pagos', 'PAGOS'),
)

AVISO_EN_REVISION = {
    'es': 'Esta política está en revisión y no debe citarse. Deriva la consulta a una persona.',
    'en': 'This policy is under review and must not be quoted. Hand the question over to a person.',
}

# Palabras que no distinguen un producto de otro. Se descartan al comparar el
# mensaje con el catalogo; la lista es corta a proposito.
_PALABRAS_VACIAS = frozenset({
    'para', 'con', 'una', 'uno', 'unos', 'unas', 'que', 'los', 'las', 'del', 'por', 'sin',
    'quiero', 'busco', 'necesito', 'tengo', 'hasta', 'mas', 'mil', 'algo', 'como', 'esta',
    'este', 'estoy', 'hay', 'talla', 'color', 'precio', 'tienen', 'tienes', 'the', 'and',
    'for', 'with', 'want', 'need', 'looking', 'size', 'any', 'have', 'you', 'some',
})

_ESPACIOS = re.compile(r'\s+')


def precio_texto(valor):
    """Precio como texto decimal con al menos 2 decimales y sin ceros de mas
    (`400000.00`, `1500.5000` -> `1500.50`). Nunca float: un float pierde
    exactitud y el Coach solo debe repetir lo que la tienda dice."""
    texto = f'{Decimal(valor).quantize(Decimal("0.0001")):f}'
    entero, _, decimales = texto.partition('.')
    decimales = decimales.rstrip('0').ljust(2, '0')
    return f'{entero}.{decimales}'


def descripcion_corta(texto, maximo=contrato.MAX_LARGO_DESCRIPCION):
    """Descripcion en una sola linea, cortada en el limite de una palabra."""
    limpia = _ESPACIOS.sub(' ', texto or '').strip()
    if len(limpia) <= maximo:
        return limpia
    corte = limpia[: maximo - 1].rsplit(' ', 1)[0].rstrip(' ,;:.')
    return f'{corte}…'


def normalizar(texto):
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in descompuesto if not unicodedata.combining(c)).lower()


def terminos_del_mensaje(mensaje):
    """Palabras del mensaje que sirven para comparar con el catalogo."""
    palabras = re.findall(r'[a-z0-9]+', normalizar(mensaje))
    return {p for p in palabras if len(p) >= 3 and p not in _PALABRAS_VACIAS}


def _productos_del_catalogo():
    return list(
        storefront_products()
        .select_related('category', 'brand')
        .prefetch_related(
            Prefetch('variants', queryset=catalog_variants_queryset()),
            'tags',
        )
        .order_by('-featured', *ORDEN_DEL_PANEL)[:MAX_PRODUCTOS_LEIDOS]
    )


def _variantes_activas(producto):
    return [v for v in producto.variants.all() if v.is_active]


def _tiene_stock(producto):
    return any(variant_stock(v) > 0 for v in _variantes_activas(producto))


def _texto_de_busqueda(producto):
    partes = [producto.name, producto.category.name]
    if producto.brand_id:
        partes.append(producto.brand.name)
    partes.extend(tag.name for tag in producto.tags.all())
    return normalizar(' '.join(partes))


def _afinidad(producto, terminos):
    """Cuantas palabras distintas del mensaje aparecen en el producto."""
    if not terminos:
        return 0
    texto = _texto_de_busqueda(producto)
    return sum(1 for termino in terminos if termino in texto)


def _candidato(producto, incluir_agotadas=False):
    """El producto como lo ve el Coach, o `None` si no hay nada que ofrecer.

    Solo viajan las variantes con existencias. Una excepcion: el producto que
    el visitante esta mirando puede viajar agotado (`incluir_agotadas`), con
    todas sus variantes en 0, para que el agente diga que no hay en vez de no
    saber de que producto se habla."""
    activas = _variantes_activas(producto)
    con_stock = [v for v in activas if variant_stock(v) > 0]
    elegidas = con_stock or (activas if incluir_agotadas else [])
    if not elegidas:
        return None
    elegidas = sorted(elegidas, key=lambda v: (size_sort_key(v.size), v.color))
    elegidas = elegidas[: contrato.MAX_VARIANTES_POR_CANDIDATO]
    return {
        'product_id': producto.id,
        'name': producto.name,
        'price': precio_texto(min(v.effective_price for v in elegidas)),
        'description': descripcion_corta(producto.description),
        'url': reverse('tienda:producto_detail', args=[producto.id]),
        'variants': [_variante(v) for v in elegidas],
    }


def _variante(v):
    datos = {
        'id': v.id,
        'size': v.size,
        'color': v.color,
        'price': precio_texto(v.effective_price),
        'available': variant_stock(v),
    }
    # Solo si hay un descuento real y vigente: el agente puede decir "antes X,
    # ahora Y" sin calcular nada.
    if v.has_discount:
        datos['list_price'] = precio_texto(v.list_price)
    return datos


MAX_PROMOCIONES = 5


def promociones(momento=None):
    """Cupones de libre acceso que el vendedor puede mencionar.

    Libre acceso = activo, vigente, con usos disponibles, sin afiliado y sin
    segmento de clientes. Los cupones de afiliados son de ellos y nunca viajan."""
    momento = momento or timezone.now()
    filas = []
    for cupon in Coupon.objects.filter(is_active=True, afiliado__isnull=True, customer_segment__isnull=True).order_by('ends_at', 'code'):
        # Un codigo fuera del formato del contrato se omite: nunca debe tumbar el turno.
        if not cupon.is_usable(momento) or not re.fullmatch(r'[A-Z0-9_-]{1,30}', cupon.code or ''):
            continue
        filas.append({
            'code': cupon.code,
            'discount_type': cupon.discount_type,
            'value': precio_texto(cupon.value),
            'min_purchase': precio_texto(cupon.min_purchase) if cupon.min_purchase is not None else None,
            'ends_on': timezone.localdate(cupon.ends_at).isoformat() if cupon.ends_at else None,
        })
        if len(filas) >= MAX_PROMOCIONES:
            break
    return filas


def candidatos(mensaje, foco_id=None, ids_carrito=(), limite=contrato.MAX_CANDIDATOS):
    """Hasta `limite` productos para el turno, en orden de prioridad.

    El orden importa: si el paquete no cabe en el presupuesto, se descartan
    primero los del final, es decir los que menos tienen que ver con el
    visitante."""
    productos = _productos_del_catalogo()
    por_id = {p.id: p for p in productos}
    elegidos = []
    vistos = set()

    def agregar(producto, incluir_agotadas=False):
        if producto is None or producto.id in vistos or len(elegidos) >= limite:
            return
        candidato = _candidato(producto, incluir_agotadas=incluir_agotadas)
        if candidato is not None:
            vistos.add(producto.id)
            elegidos.append(candidato)

    agregar(por_id.get(foco_id), incluir_agotadas=True)
    for id_producto in ids_carrito:
        agregar(por_id.get(id_producto))

    terminos = terminos_del_mensaje(mensaje)
    con_afinidad = [
        (afinidad, posicion, producto)
        for posicion, producto in enumerate(productos)
        if (afinidad := _afinidad(producto, terminos)) > 0
    ]
    for _, _, producto in sorted(con_afinidad, key=lambda t: (-t[0], t[1])):
        agregar(producto)

    for producto in productos:
        agregar(producto)
    return elegidos


def _texto_de_politica(politica):
    """Resumen y secciones de una politica en un solo texto."""
    partes = [politica['summary']]
    for seccion in politica['sections']:
        partes.append(f"{seccion['title']}: {' '.join(seccion['paragraphs'])}")
    return '\n'.join(partes)


def politicas(idioma, pendientes=None):
    """Las politicas vigentes en el idioma pedido.

    `pendientes` son las claves aun no validadas por asesoria juridica (por
    defecto `settings.VENDEDOR_POLITICAS_PENDIENTES`): viajan con
    `review_status: pending_review` y un aviso en lugar de su texto."""
    modulo = politicas_en if idioma == 'en' else politicas_es
    if pendientes is None:
        pendientes = getattr(settings, 'VENDEDOR_POLITICAS_PENDIENTES', [])
    version = modulo.ACTUALIZADO
    resultado = []
    for clave, constante in POLITICAS:
        politica = getattr(modulo, constante)
        en_revision = clave in pendientes
        resultado.append({
            'key': clave,
            'title': politica['title'],
            'text': AVISO_EN_REVISION[idioma] if en_revision else _texto_de_politica(politica),
            'version': version,
            'review_status': 'pending_review' if en_revision else 'validated',
        })
    return resultado


def afirmaciones_prohibidas():
    """Lista de afirmaciones sobre el textil que no se pueden hacer, con una
    huella de version para que el Coach detecte si cambio."""
    terminos = sorted(set(PROHIBIDAS))
    huella = hashlib.sha256('\n'.join(terminos).encode('utf-8')).hexdigest()[:12]
    return {'version': f'sha256:{huella}', 'prohibited': terminos}
