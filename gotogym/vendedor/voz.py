"""Dictado por voz de respaldo: transcribir una nota de voz corta.

El panel usa primero el dictado del navegador. Donde no lo hay, graba la voz,
la convierte en el propio navegador a WAV PCM de 16 kHz y un canal (el formato
que acepta el reconocimiento de voz del Coach sin conversiones) y la envia
aqui. La tienda la valida en memoria y la reenvia firmada al Coach, que
devuelve solo el texto. El audio no se guarda ni se registra.

Solicitud (`X-Vendedor-Contract: speech-1`, misma firma HMAC que el turno)::

    {"request_id", "locale": "es" | "en", "language": "es-CO", "timestamp",
     "audio": {"media_type": "audio/wav", "sample_rate": 16000,
               "duration_ms", "data": <base64>}}

Respuesta::

    {"meta": {"status": "ok" | "error", "error_code"?, "retry_after_seconds"?},
     "text": "..."}

Un `text` vacio con estado `ok` significa que no se entendio nada.
"""
import base64
import io
import json
import re
import time
import uuid
import wave
from dataclasses import dataclass

from .contrato import IDIOMAS, MAX_LARGO_MENSAJE, ContratoInvalido

VERSION_CONTRATO_VOZ = 'speech-1'
FRECUENCIA = 16000
MAX_SEGUNDOS = 30
MIN_MILISEGUNDOS = 300
# 30 s de PCM de 16 bits a 16 kHz son 960 KB; el resto es margen de cabecera.
MAX_BYTES_SUBIDA = 1024 * 1024
MAX_BYTES_SOLICITUD = 1400 * 1024
MAX_SEGUNDOS_REINTENTO = 3600
_CODIGO = re.compile(r'^[a-z0-9_]{1,40}$')
_IDIOMA_HABLADO = re.compile(r'^[a-z]{2}-[A-Z]{2}$')


class VozInvalida(Exception):
    """`codigo`: `vacia`, `grande`, `formato`, `corta`, `larga`."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


@dataclass(frozen=True)
class AudioPreparado:
    datos: bytes
    milisegundos: int


@dataclass(frozen=True)
class Transcripcion:
    ok: bool = True
    texto: str = ''
    codigo_error: str = ''
    reintentar_en: int | None = None


def preparar(datos):
    """`AudioPreparado` si es un WAV PCM de 16 bits, mono, 16 kHz y de 0,3 a 30 s."""
    if not datos:
        raise VozInvalida('vacia')
    if len(datos) > MAX_BYTES_SUBIDA:
        raise VozInvalida('grande')
    if not (datos.startswith(b'RIFF') and datos[8:12] == b'WAVE'):
        raise VozInvalida('formato')
    try:
        with wave.open(io.BytesIO(datos), 'rb') as audio:
            canales, ancho, frecuencia, cuadros = (
                audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes())
            muestras = audio.readframes(cuadros)
    except (wave.Error, EOFError):
        raise VozInvalida('formato') from None
    if (canales, ancho, frecuencia) != (1, 2, FRECUENCIA) or len(muestras) != cuadros * 2:
        raise VozInvalida('formato')
    milisegundos = cuadros * 1000 // FRECUENCIA
    if milisegundos < MIN_MILISEGUNDOS:
        raise VozInvalida('corta')
    if milisegundos > MAX_SEGUNDOS * 1000:
        raise VozInvalida('larga')
    return AudioPreparado(datos=datos, milisegundos=milisegundos)


def idioma_hablado(idioma, region=''):
    """Etiqueta BCP 47 para el reconocimiento. La region la elige la persona en
    el panel (p. ej. es-CO, es-MX); si no encaja con el idioma del sitio se usa
    la de la tienda."""
    if _IDIOMA_HABLADO.match(region or '') and region.split('-')[0] == idioma:
        return region
    return 'en-US' if idioma == 'en' else 'es-CO'


def armar_solicitud(audio, idioma, region='', request_id=None, ahora=None):
    if idioma not in IDIOMAS:
        raise ContratoInvalido('locale')
    solicitud = {
        'request_id': request_id or str(uuid.uuid4()),
        'locale': idioma,
        'language': idioma_hablado(idioma, region),
        'timestamp': int(time.time() if ahora is None else ahora),
        'audio': {
            'media_type': 'audio/wav',
            'sample_rate': FRECUENCIA,
            'duration_ms': audio.milisegundos,
            'data': base64.b64encode(audio.datos).decode('ascii'),
        },
    }
    if len(serializar(solicitud)) > MAX_BYTES_SOLICITUD:
        raise ContratoInvalido('solicitud.tamano')
    return solicitud


def serializar(solicitud):
    return json.dumps(solicitud, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')


def validar_respuesta(datos):
    """`Transcripcion` a partir del JSON del Coach, o `ContratoInvalido`."""
    if not isinstance(datos, dict) or not isinstance(datos.get('meta'), dict):
        raise ContratoInvalido('meta')
    meta = datos['meta']
    estado = meta.get('status')
    if estado not in ('ok', 'error'):
        raise ContratoInvalido('meta.status')
    codigo = meta.get('error_code')
    codigo = codigo if isinstance(codigo, str) and _CODIGO.match(codigo) else ''
    reintentar = meta.get('retry_after_seconds')
    if reintentar is not None and not (
        isinstance(reintentar, int) and not isinstance(reintentar, bool) and 0 <= reintentar <= MAX_SEGUNDOS_REINTENTO
    ):
        raise ContratoInvalido('meta.retry_after_seconds')
    if estado == 'error':
        return Transcripcion(ok=False, codigo_error=codigo, reintentar_en=reintentar)
    texto = datos.get('text', '')
    if not isinstance(texto, str):
        raise ContratoInvalido('text')
    # Lo dictado va al campo del mensaje: mismo tope que un mensaje escrito.
    texto = ' '.join(texto.split())[:MAX_LARGO_MENSAJE]
    return Transcripcion(ok=True, texto=texto)
