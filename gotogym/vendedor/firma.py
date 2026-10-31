"""Firma de las solicitudes de la tienda al Coach.

La firma viaja en cabeceras y no dentro del cuerpo: un cuerpo que contiene su
propia firma no se puede firmar. Se firma `marca_de_tiempo + "." + cuerpo`,
donde `cuerpo` son exactamente los bytes que se envian, sin volver a
serializar. Quien verifica (el Coach, o el simulador de este repositorio) debe
leer el cuerpo crudo y no el JSON ya interpretado, o dos serializaciones
equivalentes darian firmas distintas.

La ventana de tiempo acota la reutilizacion de una solicitud capturada; la
idempotencia por `request_id` es responsabilidad de quien recibe.
"""
import hashlib
import hmac
import time

ENCABEZADO_CLAVE = 'X-Coach-Key-Id'
ENCABEZADO_MARCA = 'X-Coach-Timestamp'
ENCABEZADO_FIRMA = 'X-Coach-Signature'
ENCABEZADO_CONTRATO = 'X-Vendedor-Contract'

VENTANA_SEGUNDOS = 60


class FirmaInvalida(Exception):
    """La firma no corresponde, esta mal formada o ya caduco. `motivo` es un
    codigo corto y estable ('malformada', 'expirada', 'no_coincide'); nunca
    incluye el cuerpo ni la firma esperada."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


class SecretoNoConfigurado(Exception):
    """Falta la clave o el secreto de servicio: no se puede firmar."""


def _mensaje(marca, cuerpo):
    return str(marca).encode('ascii') + b'.' + cuerpo


def firmar(secreto, marca, cuerpo):
    """HMAC-SHA256 en hexadecimal de `marca.cuerpo`."""
    if not secreto:
        raise SecretoNoConfigurado('Falta COACH_SERVICE_SECRET.')
    return hmac.new(secreto.encode('utf-8'), _mensaje(marca, cuerpo), hashlib.sha256).hexdigest()


def encabezados_firmados(clave_id, secreto, cuerpo, ahora=None):
    """Cabeceras de autenticacion para enviar `cuerpo` al Coach."""
    if not clave_id:
        raise SecretoNoConfigurado('Falta COACH_SERVICE_KEY_ID.')
    marca = int(time.time() if ahora is None else ahora)
    return {
        ENCABEZADO_CLAVE: clave_id,
        ENCABEZADO_MARCA: str(marca),
        ENCABEZADO_FIRMA: firmar(secreto, marca, cuerpo),
    }


def verificar(secreto, marca, cuerpo, firma, ahora=None, ventana=VENTANA_SEGUNDOS):
    """Lanza `FirmaInvalida` si la firma no corresponde o la marca esta fuera
    de la ventana. Es la implementacion de referencia para el lado receptor."""
    try:
        marca_entera = int(marca)
    except (TypeError, ValueError):
        raise FirmaInvalida('malformada') from None
    if not isinstance(firma, str) or not firma:
        raise FirmaInvalida('malformada')

    actual = time.time() if ahora is None else ahora
    if abs(actual - marca_entera) > ventana:
        raise FirmaInvalida('expirada')

    esperada = firmar(secreto, marca_entera, cuerpo)
    if not hmac.compare_digest(esperada.encode('ascii'), firma.encode('utf-8', 'ignore')):
        raise FirmaInvalida('no_coincide')
