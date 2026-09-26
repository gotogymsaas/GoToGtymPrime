"""Etiquetas para servir imagenes responsivas.

Emiten un <picture> con AVIF y WebP en varios anchos y dejan el archivo
original como respaldo del <img>. Si una imagen no tiene derivados en el
manifiesto, se emite el <img> de siempre: la plantilla no tiene que saber
si el pipeline se ejecuto.
"""
from urllib.parse import quote

from django import template
from django.conf import settings
from django.core.files.storage import default_storage
from django.templatetags.static import static

from tienda.imagenes import FORMATOS, entrada

register = template.Library()

PREFIJO_EDITORIAL = 'media/products/Imagenes Home'


def _construir(clave, respaldo, alt, sizes, clase, prioridad, cargar):
    registro = entrada(clave)
    fuentes = []
    ancho = alto = None

    if registro:
        ancho, alto = registro.get('ancho'), registro.get('alto')
        nombre_derivado = registro['nombre']
        for extension, _formato_pil, tipo in FORMATOS:
            anchos = registro['formatos'].get(extension) or []
            if not anchos:
                continue
            srcset = ', '.join(
                f'{static(f"derivados/{nombre_derivado}-{a}.{extension}")} {a}w'
                for a in anchos
            )
            fuentes.append({'tipo': tipo, 'srcset': srcset})

    return {
        'fuentes': fuentes,
        'respaldo': respaldo,
        'alt': alt or '',
        'sizes': sizes,
        'clase': clase,
        'ancho': ancho,
        'alto': alto,
        # El hero es el elemento que define el LCP: se pide con prioridad
        # alta y sin carga diferida. El resto va diferido.
        'cargar': 'eager' if prioridad else cargar,
        'prioridad': 'high' if prioridad else '',
    }


def _clave_y_respaldo_producto(nombre):
    """Clave de manifiesto y URL real para una imagen de catalogo.

    El catalogo original se poblo con fotos empaquetadas como estatico bajo
    `static/product_media/`, con derivados AVIF/WebP pre-generados por
    `generar_derivados_imagen` y registrados en el manifiesto. Un producto
    creado o editado desde el panel admin sube su foto a `MEDIA_ROOT` (el
    almacenamiento normal de Django para archivos subidos en runtime), no a
    ese directorio estatico -- nunca va a tener entrada en el manifiesto,
    porque nadie corrio ese comando sobre un archivo que no existia todavia
    en tiempo de build.

    Por eso el respaldo no puede asumir siempre static/product_media/: si
    hay manifiesto se usa el derivado (imagen del catalogo original,
    optimizada); si no hay manifiesto se sirve el archivo real desde su
    storage (MEDIA_URL), que es donde efectivamente vive. Usado tanto por
    `imagen_producto` (la tarjeta de catalogo) como por `url_imagen_producto`
    (la galeria de la ficha de producto), para no repetir esta decision en
    dos lugares.
    """
    nombre_normalizado = str(nombre).replace('\\', '/')
    clave = f'product_media/{nombre_normalizado}'
    respaldo = static(f'product_media/{nombre}') if entrada(clave) else default_storage.url(nombre_normalizado)
    return clave, respaldo


@register.simple_tag
def url_imagen_producto(nombre):
    """URL real de una imagen de catalogo, sin el <picture> con derivados
    (para plantillas que ya arman su propia galeria/lightbox, como la
    ficha de producto)."""
    if not nombre:
        return static('images/img/placeholder.webp')
    _clave, respaldo = _clave_y_respaldo_producto(nombre)
    return respaldo


@register.inclusion_tag('partials/_picture.html')
def imagen_producto(nombre, alt='', sizes='100vw', clase='', prioridad=False, cargar='lazy'):
    """Imagen de catalogo, con <picture> AVIF/WebP cuando hay derivados."""
    if not nombre:
        return {'fuentes': [], 'respaldo': static('images/img/placeholder.webp'),
                'alt': alt, 'sizes': sizes, 'clase': clase, 'ancho': None,
                'alto': None, 'cargar': cargar, 'prioridad': ''}
    clave, respaldo = _clave_y_respaldo_producto(nombre)
    return _construir(
        clave=clave,
        respaldo=respaldo,
        alt=alt, sizes=sizes, clase=clase, prioridad=prioridad, cargar=cargar,
    )


@register.inclusion_tag('partials/_picture.html')
def imagen_editorial(archivo, alt='', sizes='100vw', clase='', prioridad=False, cargar='lazy'):
    """Fotografia editorial del Home, servida desde MEDIA_ROOT."""
    respaldo = f'{settings.MEDIA_URL}products/Imagenes%20Home/{quote(archivo)}'
    return _construir(
        clave=f'{PREFIJO_EDITORIAL}/{archivo}',
        respaldo=respaldo,
        alt=alt, sizes=sizes, clase=clase, prioridad=prioridad, cargar=cargar,
    )


@register.simple_tag
def precarga_editorial(archivo, media='', ancho=1280, extension='avif'):
    """URL del derivado concreto que conviene precargar para el LCP.

    Devuelve cadena vacia si no hay derivado, para que la plantilla no
    emita un <link rel=preload> hacia un archivo inexistente (que seria
    una descarga desperdiciada y un aviso en consola).
    """
    registro = entrada(f'{PREFIJO_EDITORIAL}/{archivo}')
    if not registro:
        return ''
    anchos = registro['formatos'].get(extension) or []
    if not anchos:
        return ''
    elegido = min(anchos, key=lambda a: abs(a - ancho))
    nombre_derivado = registro['nombre']
    return static(f'derivados/{nombre_derivado}-{elegido}.{extension}')


@register.inclusion_tag('partials/_picture.html')
def imagen_hero(escritorio, movil='', alt='', sizes='100vw', clase='',
                corte='(max-width: 720px)'):
    """Hero del Home, con direccion de arte.

    El Home no reencuadra la misma foto en movil: usa otra distinta. Eso
    obliga a que las fuentes de la version movil vayan primero y con su
    propio `media`, porque el navegador se queda con el primer <source>
    que case; un srcset no basta para elegir entre dos fotografias.
    """
    base = _construir(
        clave=f'{PREFIJO_EDITORIAL}/{escritorio}',
        respaldo=f'{settings.MEDIA_URL}products/Imagenes%20Home/{quote(escritorio)}',
        alt=alt, sizes=sizes, clase=clase, prioridad=True, cargar='eager',
    )

    if movil:
        estrechas = _construir(
            clave=f'{PREFIJO_EDITORIAL}/{movil}',
            respaldo='', alt=alt, sizes=sizes, clase=clase,
            prioridad=True, cargar='eager',
        )
        for fuente in estrechas['fuentes']:
            fuente['media'] = corte
        base['fuentes'] = estrechas['fuentes'] + base['fuentes']

    return base
