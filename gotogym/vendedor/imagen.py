"""Preparacion de la foto que un cliente sube a Quantum Coach.

La foto nunca se guarda: se lee en memoria, se valida, se reduce y se vuelve a
codificar como JPEG sin metadatos (sin GPS, fecha ni modelo de celular) y solo
esa copia viaja al Coach. Volver a codificar tambien descarta cualquier cosa
escondida en el archivo original.

Formatos aceptados: JPEG, PNG, WEBP y HEIC/HEIF (las fotos de iPhone). Un
archivo que dice ser imagen y no lo es se rechaza sin decir por que al
cliente; el codigo corto queda para el registro.
"""
import colorsys
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

try:  # Fotos de iPhone. Sin la libreria, HEIC simplemente no se acepta.
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - la dependencia esta en requirements
    pillow_heif = None

# Lo que se acepta del navegador. El panel ya reduce la foto antes de subirla;
# el tope cubre al navegador que no pudo (HEIC en Chrome) y corta abusos.
MAX_BYTES_SUBIDA = 8 * 1024 * 1024
# Una imagen de muchos megapixeles cabe en pocos bytes y revienta la memoria
# al decodificarla (bomba de descompresion).
MAX_PIXELES = 40_000_000
MIN_LADO = 64
FORMATOS = frozenset({'JPEG', 'MPO', 'PNG', 'WEBP', 'HEIF'})

# Lo que viaja al Coach. 1024 px bastan para reconocer una prenda.
LADO_MAXIMO = 1024
CALIDAD = 82
MAX_BYTES_SALIDA = 350 * 1024


class ImagenInvalida(Exception):
    """`codigo`: `vacia`, `grande`, `formato`, `ilegible`, `dimensiones`."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


@dataclass(frozen=True)
class ImagenPreparada:
    datos: bytes
    ancho: int
    alto: int
    media_type: str = 'image/jpeg'


def _abrir(datos):
    try:
        imagen = Image.open(io.BytesIO(datos))
    except Image.DecompressionBombError:
        raise ImagenInvalida('dimensiones') from None
    except (UnidentifiedImageError, OSError, ValueError):
        raise ImagenInvalida('formato') from None
    if imagen.format not in FORMATOS:
        raise ImagenInvalida('formato')
    ancho, alto = imagen.size
    if ancho * alto > MAX_PIXELES:
        raise ImagenInvalida('dimensiones')
    if min(ancho, alto) < MIN_LADO:
        raise ImagenInvalida('dimensiones')
    return imagen


def _a_rgb(imagen):
    """RGB sobre fondo blanco: una prenda recortada (PNG con transparencia) no
    debe quedar sobre negro, que cambiaria su color aparente."""
    if imagen.mode in ('RGBA', 'LA') or (imagen.mode == 'P' and 'transparency' in imagen.info):
        imagen = imagen.convert('RGBA')
        fondo = Image.new('RGB', imagen.size, (255, 255, 255))
        fondo.paste(imagen, mask=imagen.getchannel('A'))
        return fondo
    return imagen.convert('RGB')


def _codificar(imagen, lado, calidad):
    copia = imagen.copy()
    copia.thumbnail((lado, lado), Image.Resampling.LANCZOS)
    salida = io.BytesIO()
    # Sin `exif=` ni `icc_profile=`: el JPEG sale sin metadatos.
    copia.save(salida, format='JPEG', quality=calidad, optimize=True)
    return salida.getvalue(), copia.size


def preparar(datos):
    """`ImagenPreparada` lista para enviar, o `ImagenInvalida`."""
    if not datos:
        raise ImagenInvalida('vacia')
    if len(datos) > MAX_BYTES_SUBIDA:
        raise ImagenInvalida('grande')
    imagen = _abrir(datos)
    try:
        imagen.load()
        # La orientacion del EXIF se aplica a los pixeles antes de borrarlo:
        # si no, una foto vertical llegaria acostada.
        imagen = _a_rgb(ImageOps.exif_transpose(imagen))
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ImagenInvalida('ilegible') from None

    for lado, calidad in ((LADO_MAXIMO, CALIDAD), (768, 75), (512, 70)):
        codificada, (ancho, alto) = _codificar(imagen, lado, calidad)
        if len(codificada) <= MAX_BYTES_SALIDA:
            return ImagenPreparada(datos=codificada, ancho=ancho, alto=alto)
    raise ImagenInvalida('grande')


def color_dominante(datos):
    """Familia de color del centro de la imagen (products.atributos.COLORES).

    Solo para el Coach simulado de desarrollo y pruebas: un promedio de
    pixeles no es vision artificial."""
    imagen = Image.open(io.BytesIO(datos)).convert('RGB')
    ancho, alto = imagen.size
    centro = imagen.crop((ancho // 4, alto // 4, ancho - ancho // 4, alto - alto // 4))
    r, g, b = centro.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    return familia_de_rgb(r, g, b)


def familia_de_rgb(r, g, b):
    tono, luz, saturacion = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if luz < 0.18:
        return 'negro'
    if luz > 0.85 and saturacion < 0.35:
        return 'blanco'
    if saturacion < 0.18:
        return 'gris'
    grados = tono * 360
    if grados < 15 or grados >= 345:
        return 'rojo'
    if grados < 40:
        return 'naranja' if luz >= 0.35 else 'cafe'
    if grados < 65:
        return 'amarillo' if saturacion >= 0.45 or luz < 0.7 else 'beige'
    if grados < 170:
        return 'verde'
    if grados < 260:
        return 'azul'
    if grados < 300:
        return 'morado'
    return 'rosa'
