"""Derivados responsivos de las imagenes del sitio.

El catalogo y las fotografias editoriales se servian tal cual se subieron:
JPEG de hasta 1,7 MB para una tarjeta que se pinta a 300 px de ancho, y
nombres de WhatsApp en la URL. Este modulo define de donde salen los
derivados y como se nombran; el comando `generar_derivados_imagen` los
crea y la etiqueta `{% imagen_producto %}` los sirve.

Decisiones:

- Los derivados viven bajo `static/derivados/`, tengan su origen en
  `static/product_media/` o en `media/`. Asi la plantilla siempre resuelve
  una sola clase de URL y el resultado es un artefacto de build servido
  como estatico, que es lo que es.

- El nombre del derivado se construye desde la ruta de origen, en minuscula
  y sin espacios: `Imagenes Home/WhatsApp Image ... (2).jpeg` deja de
  aparecer en la URL publica.

- Un manifiesto JSON registra que anchos y formatos existen de verdad. La
  etiqueta lo consulta antes de emitir un <source>: si un srcset apunta a
  un archivo que no existe, el navegador no cae al <img> de respaldo, sino
  que muestra la imagen rota. Con el manifiesto, una imagen sin derivados
  se sirve como un <img> normal.
"""
import json
import re
import unicodedata
from pathlib import Path

from django.conf import settings

# Cubren desde una tarjeta en movil hasta un hero a pantalla completa en
# una pantalla de alta densidad. Un ancho mayor que el original no se
# genera: agrandar no anade detalle y si peso.
ANCHOS = (400, 640, 960, 1280, 1920)

# AVIF primero: el navegador elige el primer <source> que entiende, y es
# el que menos pesa. WebP cubre lo que no soporta AVIF y el original
# JPEG/PNG queda como ultimo respaldo en el <img>.
FORMATOS = (
    ('avif', 'AVIF', 'image/avif'),
    ('webp', 'WEBP', 'image/webp'),
)

CARPETA_DERIVADOS = 'derivados'
NOMBRE_MANIFIESTO = 'manifiesto.json'

_manifiesto_cache = None


def raiz_estaticos():
    """Directorio de estaticos del proyecto (no el de collectstatic)."""
    return Path(settings.BASE_DIR) / 'static'


def raiz_derivados():
    return raiz_estaticos() / CARPETA_DERIVADOS


def ruta_manifiesto():
    return raiz_derivados() / NOMBRE_MANIFIESTO


def clave_desde_ruta(ruta_relativa):
    """Nombre publico y estable a partir de la ruta de origen.

    'product_media/products/IMG_9347_2.jpg' -> 'product_media-products-img-9347-2'
    """
    texto = str(ruta_relativa).replace('\\', '/')
    texto = texto.rsplit('.', 1)[0]
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9]+', '-', texto)
    return texto.strip('-')


def cargar_manifiesto(forzar=False):
    """Lee el manifiesto una vez por proceso.

    Se cachea porque la etiqueta lo consulta una vez por imagen y una
    parrilla de catalogo son decenas de consultas por peticion.
    """
    global _manifiesto_cache
    if _manifiesto_cache is not None and not forzar:
        return _manifiesto_cache

    destino = ruta_manifiesto()
    try:
        with open(destino, encoding='utf-8') as archivo:
            _manifiesto_cache = json.load(archivo)
    except (OSError, ValueError):
        # Sin manifiesto el sitio sigue funcionando: cada imagen se sirve
        # como el original, igual que antes de existir este pipeline.
        _manifiesto_cache = {}
    return _manifiesto_cache


def limpiar_cache():
    global _manifiesto_cache
    _manifiesto_cache = None


def entrada(ruta_origen):
    """Devuelve el registro del manifiesto para una ruta de origen."""
    return cargar_manifiesto().get(str(ruta_origen).replace('\\', '/'))
