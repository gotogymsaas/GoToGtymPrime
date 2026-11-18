"""Contrato de vision entre la tienda y el Coach: describir una foto de prenda.

Es una llamada aparte del turno de conversacion (`contrato.py`) por dos
motivos: una foto no cabe en el presupuesto de 24 KB del turno, y el Coach
solo debe devolver atributos de un vocabulario cerrado, nunca productos. La
tienda compara esos atributos con su catalogo y arma el turno normal con lo
que encontro (`visual_query`).

Solicitud (`X-Vendedor-Contract: vision-1`, misma firma HMAC que el turno)::

    {"request_id", "purpose": "similar_products" | "catalog_attributes",
     "locale": "es" | "en", "timestamp",
     "image": {"media_type": "image/jpeg", "width", "height", "data": <base64>},
     "vocabulary": {"version", "garment_type": [...], "sleeve": [...], ...}}

Respuesta::

    {"meta": {"status": "ok" | "error", "error_code"?, "retry_after_seconds"?},
     "garment_detected": bool, "person_present": bool,
     "attributes": {"garment_type"?, "sleeve"?, "neckline"?, "fit"?,
                    "pattern"?, "colors"?: [...], "line_hint"?},
     "confidence": 0..1}

Un atributo fuera del vocabulario se descarta (no invalida la respuesta). Ni la
solicitud ni la respuesta llevan datos de la persona.
"""
import base64
import json
import re
import time
import uuid
from dataclasses import dataclass, field

from products import atributos

from .contrato import IDIOMAS, ContratoInvalido

VERSION_CONTRATO_VISION = 'vision-1'
PROPOSITOS = frozenset({'similar_products', 'catalog_attributes'})
MAX_BYTES_SOLICITUD = 512 * 1024
MAX_SEGUNDOS_REINTENTO = 3600
_CODIGO = re.compile(r'^[a-z0-9_]{1,40}$')


@dataclass(frozen=True)
class Descripcion:
    """Lo que el Coach vio en la foto, ya reducido al vocabulario."""
    ok: bool = True
    prenda: bool = False
    persona: bool = False
    atributos: dict = field(default_factory=dict)
    confianza: float = 0.0
    codigo_error: str = ''
    reintentar_en: int | None = None


def armar_solicitud(imagen, idioma, proposito='similar_products', request_id=None, ahora=None):
    if proposito not in PROPOSITOS:
        raise ContratoInvalido('purpose')
    if idioma not in IDIOMAS:
        raise ContratoInvalido('locale')
    solicitud = {
        'request_id': request_id or str(uuid.uuid4()),
        'purpose': proposito,
        'locale': idioma,
        'timestamp': int(time.time() if ahora is None else ahora),
        'image': {
            'media_type': imagen.media_type,
            'width': imagen.ancho,
            'height': imagen.alto,
            'data': base64.b64encode(imagen.datos).decode('ascii'),
        },
        'vocabulary': atributos.vocabulario(),
    }
    if len(serializar(solicitud)) > MAX_BYTES_SOLICITUD:
        raise ContratoInvalido('solicitud.tamano')
    return solicitud


def serializar(solicitud):
    return json.dumps(solicitud, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')


def validar_respuesta(datos):
    """`Descripcion` a partir del JSON del Coach, o `ContratoInvalido`."""
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
        return Descripcion(ok=False, codigo_error=codigo, reintentar_en=reintentar)

    prenda = datos.get('garment_detected')
    persona = datos.get('person_present', False)
    if not isinstance(prenda, bool):
        raise ContratoInvalido('garment_detected')
    if not isinstance(persona, bool):
        raise ContratoInvalido('person_present')
    confianza = datos.get('confidence', 0)
    if isinstance(confianza, bool) or not isinstance(confianza, (int, float)) or not 0 <= confianza <= 1:
        raise ContratoInvalido('confidence')
    limpios = atributos.limpiar(datos.get('attributes'))
    return Descripcion(
        ok=True,
        prenda=prenda,
        persona=persona,
        atributos=limpios if prenda else {},
        confianza=float(confianza),
    )
