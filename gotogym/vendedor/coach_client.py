"""Clientes del servicio de IA (Coach).

Hay dos implementaciones con la misma interfaz (`enviar(solicitud)`):

* `ClienteHttp` habla con el Coach real: firma el cuerpo, espera con un
  tiempo maximo y no reintenta. Un reintento automatico de un mensaje que
  quiza si llego duplicaria turnos y costo; si falla, el visitante decide.
* `ClienteSimulado` cumple el contrato sin red, a partir de los candidatos
  del propio paquete. Existe para desarrollar y probar la interfaz mientras
  el Coach no este disponible. Nunca atiende a clientes reales: solo se elige
  con `VENDEDOR_COACH_SIMULADO` (que por defecto vale solo en desarrollo y
  pruebas).

Todo fallo se informa con `CoachNoDisponible` y un codigo corto. Ningun
mensaje de error incluye el texto del visitante ni el cuerpo de la respuesta.
"""
import logging
from decimal import Decimal
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core.cache import cache

from . import contrato, firma

logger = logging.getLogger(__name__)

# Fallos seguidos que abren el circuito, y cuanto dura abierto. Mientras esta
# abierto no se llama al Coach: cada intento fallido ocupa un worker hasta el
# tiempo maximo y la tienda solo tiene dos.
FALLOS_PARA_ABRIR = 5
SEGUNDOS_CIRCUITO = 60
_CLAVE_FALLOS = 'vendedor:coach:fallos'
_CLAVE_CIRCUITO = 'vendedor:coach:abierto'

MAX_RETRY_AFTER = 3600

PALABRA_ERROR_SIMULADO = '[simular-error]'
PALABRA_MALICIOSO_SIMULADO = '[simular-malicioso]'


class CoachNoDisponible(Exception):
    """El Coach no pudo atender el turno. `codigo` es uno de: `no_configurado`,
    `circuito_abierto`, `timeout`, `conexion`, `rechazado` (4xx), `servicio`
    (5xx), `limite` (429), `respuesta_invalida`, `error_del_coach`."""

    def __init__(self, codigo, reintentar_en=None):
        super().__init__(codigo)
        self.codigo = codigo
        self.reintentar_en = reintentar_en


# --- Circuito de corte -----------------------------------------------------

def circuito_abierto():
    return bool(cache.get(_CLAVE_CIRCUITO))


def registrar_fallo():
    cache.add(_CLAVE_FALLOS, 0, timeout=SEGUNDOS_CIRCUITO)
    try:
        fallos = cache.incr(_CLAVE_FALLOS)
    except ValueError:
        cache.set(_CLAVE_FALLOS, 1, timeout=SEGUNDOS_CIRCUITO)
        fallos = 1
    if fallos >= FALLOS_PARA_ABRIR and cache.add(_CLAVE_CIRCUITO, 1, timeout=SEGUNDOS_CIRCUITO):
        logger.error('Vendedor: circuito del Coach abierto tras %s fallos seguidos.', fallos)


def registrar_exito():
    cache.delete(_CLAVE_FALLOS)


# --- Cliente real ------------------------------------------------------------

def _url_permitida(url):
    """HTTPS siempre; HTTP solo hacia la propia maquina (para probar un Coach
    local). Una solicitud firmada no debe viajar sin cifrar por una red."""
    partes = urlsplit(url)
    if partes.scheme == 'https' and partes.netloc:
        return True
    return partes.scheme == 'http' and partes.hostname in ('localhost', '127.0.0.1', '::1')


def _segundos_de_espera(cabecera):
    try:
        return max(0, min(int(cabecera), MAX_RETRY_AFTER))
    except (TypeError, ValueError):
        return None


class ClienteHttp:
    def __init__(self, url, clave_id, secreto, timeout):
        self.url = url
        self.clave_id = clave_id
        self.secreto = secreto
        self.timeout = timeout

    def enviar(self, solicitud):
        """`RespuestaCoach` ya validada en su forma, o `CoachNoDisponible`."""
        if not _url_permitida(self.url):
            raise CoachNoDisponible('no_configurado')
        cuerpo = contrato.serializar(solicitud)
        try:
            cabeceras = firma.encabezados_firmados(self.clave_id, self.secreto, cuerpo)
        except firma.SecretoNoConfigurado:
            raise CoachNoDisponible('no_configurado') from None
        cabeceras['Content-Type'] = 'application/json; charset=utf-8'
        cabeceras['Accept'] = 'application/json'
        cabeceras[firma.ENCABEZADO_CONTRATO] = (
            contrato.VERSION_CONTRATO_V2 if 'identity' in solicitud else contrato.VERSION_CONTRATO
        )

        try:
            respuesta = requests.post(
                self.url,
                data=cuerpo,
                headers=cabeceras,
                timeout=(min(3.0, self.timeout), self.timeout),
                # Una redireccion reenviaria la solicitud firmada a otro destino.
                allow_redirects=False,
            )
        except requests.ConnectTimeout:
            # No se llego a hablar con el Coach: es un problema de red, no
            # de lentitud al responder.
            raise CoachNoDisponible('conexion') from None
        except requests.Timeout:
            raise CoachNoDisponible('timeout') from None
        except requests.RequestException:
            raise CoachNoDisponible('conexion') from None

        estado = respuesta.status_code
        if estado == 429:
            raise CoachNoDisponible('limite', _segundos_de_espera(respuesta.headers.get('Retry-After')))
        if estado >= 500:
            raise CoachNoDisponible('servicio')
        if estado != 200:
            # 3xx, 401, 403, 400...: la tienda y el Coach no se entienden
            # (firma, clave, contrato). Es un problema de configuracion.
            logger.error('Vendedor: el Coach respondio HTTP %s.', estado)
            raise CoachNoDisponible('rechazado')

        try:
            datos = respuesta.json()
        except ValueError:
            raise CoachNoDisponible('respuesta_invalida') from None
        try:
            validada = contrato.validar_respuesta(datos)
        except contrato.ContratoInvalido as error:
            logger.error('Vendedor: respuesta del Coach fuera de contrato (%s).', error)
            raise CoachNoDisponible('respuesta_invalida') from None
        if not validada.ok:
            raise CoachNoDisponible('error_del_coach', validada.meta.reintentar_en)
        return validada


# --- Cliente simulado --------------------------------------------------------

def respuesta_simulada(solicitud):
    """Cuerpo de respuesta (dict del contrato) que un Coach de mentira daria a
    `solicitud`: lo que hay en el paquete, rotulado como simulado."""
    candidatos = solicitud['evidence']['candidates']
    if not candidatos:
        texto = (
            '[Respuesta simulada] No tengo productos con existencias para mostrarte '
            'en este momento. No es una respuesta del Coach real.'
        )
        return {'reply': texto, 'meta': {'status': 'ok', 'agents_used': ['simulado']}}

    primero = candidatos[0]
    precio = f"{int(Decimal(primero['price'])):,}".replace(',', '.')
    con_stock = [v for v in primero['variants'] if v['available'] > 0]
    texto = (
        f"[Respuesta simulada] Podría interesarte {primero['name']}, desde "
        f"${precio}. No es una respuesta del Coach real."
    )
    acciones = [{'type': 'open_product', 'product_id': primero['product_id']}]
    if con_stock and not solicitud['shop_flags']['purchases_paused']:
        acciones.append({'type': 'add_to_cart', 'variant_id': con_stock[0]['id']})
    if solicitud['cart']['count']:
        acciones.append({'type': 'go_checkout'})
    return {
        'reply': texto,
        'ui_actions': acciones,
        'product_cards': [
            {'product_id': c['product_id'], 'reason': 'Simulado: producto con existencias.'}
            for c in candidatos[:3]
        ],
        'meta': {'status': 'ok', 'agents_used': ['simulado'], 'evidence_refs': []},
    }


def respuesta_maliciosa_simulada():
    """Cuerpo de respuesta que la tienda debe rechazar o recortar: una
    afirmacion prohibida, acciones fuera de la lista blanca e ids inexistentes."""
    return {
        'reply': 'Este material tiene secado rápido y protección solar. Oferta única, ¡solo hoy!',
        'ui_actions': [
            {'type': 'apply_coupon', 'code': 'GRATIS'},
            {'type': 'add_to_cart', 'variant_id': 999999999},
            {'type': 'open_product', 'product_id': 999999999},
            {'type': 'go_checkout'},
        ],
        'product_cards': [{'product_id': 999999999, 'reason': 'No existe.'}],
        'meta': {'status': 'ok', 'agents_used': ['simulado']},
    }


class ClienteSimulado:
    """Coach de mentira. Contesta con lo que hay en el paquete y lo dice.

    Dos mensajes de prueba para ver los estados de la interfaz:
    `[simular-error]` devuelve un error con espera, y `[simular-malicioso]`
    devuelve acciones que la tienda debe descartar."""

    def enviar(self, solicitud):
        mensaje = solicitud['message']
        if PALABRA_ERROR_SIMULADO in mensaje:
            raise CoachNoDisponible('error_del_coach', 5)
        if PALABRA_MALICIOSO_SIMULADO in mensaje:
            return contrato.validar_respuesta(respuesta_maliciosa_simulada())
        return contrato.validar_respuesta(respuesta_simulada(solicitud))


def obtener_cliente():
    """El cliente que corresponde a la configuracion, o `None` si no hay
    ninguno y el vendedor debe decir que no esta disponible."""
    if settings.COACH_API_URL:
        return ClienteHttp(
            settings.COACH_API_URL,
            settings.COACH_SERVICE_KEY_ID,
            settings.COACH_SERVICE_SECRET,
            settings.VENDEDOR_TIMEOUT_SECONDS,
        )
    if settings.VENDEDOR_COACH_SIMULADO:
        return ClienteSimulado()
    return None
