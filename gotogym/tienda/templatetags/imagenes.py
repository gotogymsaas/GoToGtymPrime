"""Etiquetas para servir imagenes responsivas.

Emiten un <picture> con AVIF y WebP en varios anchos y dejan el archivo
original como respaldo del <img>. Si una imagen no tiene derivados en el
manifiesto, se emite el <img> de siempre: la plantilla no tiene que saber
si el pipeline se ejecuto.
"""
from urllib.parse import quote

from django import template
from django.conf import settings
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


@register.inclusion_tag('partials/_picture.html')
def imagen_producto(nombre, alt='', sizes='100vw', clase='', prioridad=False, cargar='lazy'):
    """Imagen de catalogo, servida desde static/product_media/."""
    if not nombre:
        return {'fuentes': [], 'respaldo': static('images/img/placeholder.webp'),
                'alt': alt, 'sizes': sizes, 'clase': clase, 'ancho': None,
                'alto': None, 'cargar': cargar, 'prioridad': ''}
    nombre_normalizado = str(nombre).replace('\\', '/')
    return _construir(
        clave=f'product_media/{nombre_normalizado}',
        respaldo=static(f'product_media/{nombre}'),
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
