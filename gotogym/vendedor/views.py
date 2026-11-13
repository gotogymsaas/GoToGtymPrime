"""Puente entre el navegador y el Coach.

El navegador nunca habla con el Coach: envia aqui el mensaje (con el token
CSRF de la sesion) y esta vista arma el paquete con datos del servidor, lo
firma, lo envia y devuelve una respuesta ya validada. Todas las respuestas son
JSON con `ok` y, si falla, un `error` de una lista corta de codigos; los textos
que ve la persona los pone el panel (traducidos), no el servidor.

Nunca se escribe el texto del mensaje en logs ni en Sentry.
"""
import json
import logging
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from gotogym.ratelimit import contar, ip_del_cliente, rate_limit

from . import coach_client, contrato, conversacion, paquete, respuesta
from .exposicion import visible_para

logger = logging.getLogger(__name__)

MAX_BYTES_CUERPO = 4096
SEGUNDOS_DIA = 24 * 60 * 60

# Codigo interno del cliente -> (codigo para el panel, estado HTTP).
_ERRORES_DEL_COACH = {
    'no_configurado': ('no_disponible', 503),
    'circuito_abierto': ('no_disponible', 503),
    'timeout': ('timeout', 504),
    'limite': ('espera', 429),
}
_ERROR_GENERICO_DEL_COACH = ('error', 502)


def _error(codigo, estado, reintentar_en=None):
    cuerpo = {'ok': False, 'error': codigo, 'contact_url': reverse('contacto')}
    if reintentar_en:
        cuerpo['retry_after'] = int(reintentar_en)
    respuesta_http = JsonResponse(cuerpo, status=estado)
    if reintentar_en:
        respuesta_http['Retry-After'] = str(int(reintentar_en))
    return respuesta_http


def _limitado(vista):
    """Limite de mensajes por minuto, mas estricto para anonimos. Se lee de la
    configuracion en cada peticion, no al importar el modulo."""
    @wraps(vista)
    def envuelta(request, *args, **kwargs):
        autenticado = request.user.is_authenticated
        por_minuto = settings.VENDEDOR_RATE_AUTH if autenticado else settings.VENDEDOR_RATE_ANON
        return rate_limit('vendedor', por_minuto, 60)(vista)(request, *args, **kwargs)
    return envuelta


def _clave_de_cliente(request):
    if request.user.is_authenticated:
        return f'user:{request.user.pk}'
    return f'ip:{ip_del_cliente(request)}'


def _ahora():
    return time.time()


def _clave_de_espera(request):
    return f'vendedor:espera:{_clave_de_cliente(request)}'


def _segundos_de_espera(request):
    """Segundos que faltan para poder escribir de nuevo tras una espera que
    pidio el Coach (0 si no hay)."""
    hasta = cache.get(_clave_de_espera(request))
    if not hasta:
        return 0
    return max(0, int(hasta - _ahora() + 0.999))


def _exigir_espera(request, segundos):
    cache.set(_clave_de_espera(request), _ahora() + segundos, timeout=segundos + 1)


def _tope_diario_superado(request):
    """Cuenta este mensaje contra el tope del dia. True si ya se paso."""
    if not getattr(settings, 'RATE_LIMIT_ENABLED', True):
        return False
    # El dia cuenta de medianoche a medianoche en la hora del sitio, no en UTC.
    desfase = int(timezone.localtime().utcoffset().total_seconds())
    usados = contar(f'vendedor:dia:{_clave_de_cliente(request)}', SEGUNDOS_DIA, desfase)
    return usados > settings.VENDEDOR_MAX_MENSAJES_DIA


def _leer_cuerpo(request):
    """`(datos, error)`. El cuerpo es un JSON pequeno; uno grande se rechaza
    sin leerlo."""
    try:
        largo = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        return None, ('solicitud_invalida', 400)
    if largo > MAX_BYTES_CUERPO:
        return None, ('solicitud_invalida', 413)
    if request.content_type != 'application/json':
        return None, ('solicitud_invalida', 415)
    try:
        datos = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return None, ('solicitud_invalida', 400)
    if not isinstance(datos, dict):
        return None, ('solicitud_invalida', 400)
    return datos, None


def _atender(request):
    datos, fallo = _leer_cuerpo(request)
    if fallo:
        return _error(*fallo)

    texto = datos.get('message')
    if not isinstance(texto, str) or not 0 < len(texto.strip()) <= contrato.MAX_LARGO_MENSAJE:
        return _error('mensaje_invalido', 400)

    cliente = coach_client.obtener_cliente()
    if cliente is None or coach_client.circuito_abierto():
        return _error('no_disponible', 503)

    espera = _segundos_de_espera(request)
    if espera:
        return _error('espera', 429, espera)
    estado = conversacion.obtener(request.session, reiniciar=datos.get('new') is True)
    if estado['turnos'] >= settings.VENDEDOR_MAX_TURNOS:
        return _error('limite_turnos', 409)
    if _tope_diario_superado(request):
        return _error('limite_diario', 429)

    try:
        solicitud = paquete.armar_solicitud(request, texto, estado['id'])
    except contrato.ContratoInvalido as error:
        logger.error('Vendedor: no se pudo armar un paquete valido (%s).', error)
        return _error('paquete_invalido', 500)

    try:
        crudo = cliente.enviar(solicitud)
    except coach_client.CoachNoDisponible as error:
        logger.warning('Vendedor: el Coach no atendio el turno (%s).', error.codigo)
        if error.codigo != 'no_configurado':
            coach_client.registrar_fallo()
        if error.reintentar_en:
            _exigir_espera(request, error.reintentar_en)
        codigo, estado_http = _ERRORES_DEL_COACH.get(error.codigo, _ERROR_GENERICO_DEL_COACH)
        return _error(codigo, estado_http, error.reintentar_en)
    coach_client.registrar_exito()

    try:
        segura = respuesta.sanear(crudo, solicitud)
    except respuesta.RespuestaRechazada as error:
        logger.warning('Vendedor: respuesta del Coach rechazada (%s).', error.codigo)
        return _error('respuesta_rechazada', 502)
    if segura.descartadas:
        logger.info('Vendedor: se descartaron %s propuestas del Coach.', segura.descartadas)

    conversacion.turno_completado(request.session, estado)
    return JsonResponse({
        'ok': True,
        'reply': segura.texto,
        'cards': segura.tarjetas,
        'actions': segura.acciones,
        'handoff': segura.contacto,
        'conversation': {'turns': estado['turnos'], 'max_turns': settings.VENDEDOR_MAX_TURNOS},
    })


@require_POST
def mensaje(request):
    # Apagado o fuera del grupo expuesto: la ruta no existe, y no se cuenta
    # nada contra el limite de uso.
    if not visible_para(request):
        raise Http404
    return _limitado(_atender)(request)
