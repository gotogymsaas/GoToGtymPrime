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
import re
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadhandler import MemoryFileUploadHandler
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_POST
from gotogym.ratelimit import contar, ip_del_cliente, rate_limit
from products import atributos

from . import (
    coach_client,
    contrato,
    conversacion,
    estado,
    evidencia,
    imagen,
    paquete,
    respuesta,
    vision,
)
from .exposicion import imagen_permitida_para, visible_para

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


_DIAGNOSTICO_PERMITIDO = re.compile(r'[^A-Za-z0-9_.:\[\]-]')


def _diagnostico_para(request, *partes):
    """Motivo tecnico del fallo, solo para el personal del sitio: sin acceso
    a los logs del servidor, es la forma de saber por que fallo un turno.
    Solo codigos y nombres de campo (nunca el mensaje ni la respuesta), y
    limpio de cualquier caracter fuera de esa forma."""
    if not getattr(request.user, 'is_staff', False):
        return ''
    texto = ':'.join(str(parte) for parte in partes if parte)
    return _DIAGNOSTICO_PERMITIDO.sub('', texto)[:120]


def _error(codigo, estado, reintentar_en=None, diagnostico=''):
    cuerpo = {'ok': False, 'error': codigo, 'contact_url': reverse('contacto')}
    if diagnostico:
        cuerpo['diagnostic'] = diagnostico
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


def _cliente_disponible(request):
    """`(cliente, None)` o `(None, respuesta_de_error)`."""
    cliente = coach_client.obtener_cliente()
    if cliente is None or coach_client.circuito_abierto():
        motivo = 'no_configurado' if cliente is None else 'circuito_abierto'
        return None, _error('no_disponible', 503, diagnostico=_diagnostico_para(request, motivo))
    return cliente, None


def _abrir_turno(request, reiniciar):
    """`(conversacion, None)` si el visitante puede hablar ahora, o
    `(None, respuesta_de_error)`. Cuenta el mensaje contra el tope del dia."""
    espera = _segundos_de_espera(request)
    if espera:
        return None, _error('espera', 429, espera)
    identity_epoch = estado.estado_usuario(request)['epoch']
    estado_conversacion = conversacion.obtener(request.session, reiniciar=reiniciar, binding=identity_epoch)
    if estado_conversacion['turnos'] >= settings.VENDEDOR_MAX_TURNOS:
        return None, _error('limite_turnos', 409)
    if _tope_diario_superado(request):
        return None, _error('limite_diario', 429)
    return estado_conversacion, None


def _completar_turno(request, cliente, texto, estado_conversacion, visual=None, extra=None):
    """Arma el paquete, lo envia al Coach y devuelve la respuesta ya saneada."""
    try:
        solicitud = paquete.armar_solicitud(request, texto, estado_conversacion['id'], visual=visual)
    except contrato.ContratoInvalido as error:
        logger.error('Vendedor: no se pudo armar un paquete valido (%s).', error)
        return _error('paquete_invalido', 500, diagnostico=_diagnostico_para(request, 'paquete_invalido', error))

    try:
        crudo = cliente.enviar(solicitud)
    except coach_client.CoachNoDisponible as error:
        logger.warning(
            'Vendedor: el Coach no atendio el turno (%s%s).',
            error.codigo, f': {error.detalle}' if error.detalle else '',
        )
        if error.codigo != 'no_configurado' and not error.es_de_contenido:
            coach_client.registrar_fallo()
        if error.reintentar_en:
            _exigir_espera(request, error.reintentar_en)
        codigo, estado_http = _ERRORES_DEL_COACH.get(error.codigo, _ERROR_GENERICO_DEL_COACH)
        return _error(codigo, estado_http, error.reintentar_en,
                      diagnostico=_diagnostico_para(request, error.codigo, error.detalle))
    coach_client.registrar_exito()

    try:
        segura = respuesta.sanear(crudo, solicitud)
    except respuesta.RespuestaRechazada as error:
        logger.warning('Vendedor: respuesta del Coach rechazada (%s).', error.codigo)
        return _error('respuesta_rechazada', 502,
                      diagnostico=_diagnostico_para(request, 'respuesta_rechazada', error.codigo))
    if segura.descartadas:
        logger.info('Vendedor: se descartaron %s propuestas del Coach.', segura.descartadas)

    conversacion.turno_completado(request.session, estado_conversacion)
    cuerpo = {
        'ok': True,
        'reply': segura.texto,
        'cards': segura.tarjetas,
        'actions': segura.acciones,
        'handoff': segura.contacto,
        'conversation': {'turns': estado_conversacion['turnos'], 'max_turns': settings.VENDEDOR_MAX_TURNOS},
    }
    cuerpo.update(extra or {})
    return JsonResponse(cuerpo)


def _atender(request):
    datos, fallo = _leer_cuerpo(request)
    if fallo:
        return _error(*fallo)

    texto = datos.get('message')
    if not isinstance(texto, str) or not 0 < len(texto.strip()) <= contrato.MAX_LARGO_MENSAJE:
        return _error('mensaje_invalido', 400)

    cliente, fallo = _cliente_disponible(request)
    if fallo:
        return fallo
    estado_conversacion, fallo = _abrir_turno(request, reiniciar=datos.get('new') is True)
    if fallo:
        return fallo
    return _completar_turno(request, cliente, texto, estado_conversacion)


# --- Busqueda por foto ---------------------------------------------------------

# La peticion trae la foto y, opcionalmente, un texto corto.
MAX_BYTES_PETICION_IMAGEN = imagen.MAX_BYTES_SUBIDA + 64 * 1024

# Codigo interno del cliente de vision -> (codigo para el panel, estado HTTP).
_ERRORES_DE_VISION = {
    'no_soportado': ('imagen_no_disponible', 503),
    'no_configurado': ('imagen_no_disponible', 503),
    'timeout': ('timeout', 504),
    'limite': ('espera', 429),
    'error_del_coach': ('imagen_rechazada', 422),
}


class _SubidaEnMemoria(MemoryFileUploadHandler):
    """La foto nunca toca el disco: se recibe entera en memoria, hasta el tope
    de la peticion. El manejador por defecto la pasaria a un archivo temporal
    por encima de FILE_UPLOAD_MAX_MEMORY_SIZE."""

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        self.activated = 0 < content_length <= MAX_BYTES_PETICION_IMAGEN


def _tope_de_imagenes_superado(request):
    """Cuenta esta foto contra el tope de la persona y el de toda la tienda."""
    if not getattr(settings, 'RATE_LIMIT_ENABLED', True):
        return False
    desfase = int(timezone.localtime().utcoffset().total_seconds())
    propias = contar(f'vendedor:imagen:dia:{_clave_de_cliente(request)}', SEGUNDOS_DIA, desfase)
    if propias > settings.VENDEDOR_IMAGEN_MAX_DIA:
        return True
    return contar('vendedor:imagen:dia:global', SEGUNDOS_DIA, desfase) > settings.VENDEDOR_IMAGEN_MAX_DIA_GLOBAL


def _mensaje_por_defecto(idioma):
    with translation.override(idioma):
        return gettext('Busco prendas parecidas a la de mi foto.')


def _atender_imagen(request):
    if request.content_type != 'multipart/form-data':
        return _error('imagen_invalida', 415)
    archivo = request.FILES.get('imagen')
    if archivo is None:
        return _error('imagen_invalida', 400)
    texto = (request.POST.get('message') or '').strip()
    if len(texto) > contrato.MAX_LARGO_MENSAJE:
        return _error('mensaje_invalido', 400)

    cliente, fallo = _cliente_disponible(request)
    if fallo:
        return fallo
    # Los topes se revisan antes de gastar una llamada al modelo de vision.
    estado_conversacion, fallo = _abrir_turno(request, reiniciar=request.POST.get('new') == '1')
    if fallo:
        return fallo
    if _tope_de_imagenes_superado(request):
        return _error('limite_imagenes', 429)

    try:
        preparada = imagen.preparar(archivo.read())
    except imagen.ImagenInvalida as error:
        grande = error.codigo == 'grande'
        return _error('imagen_grande' if grande else 'imagen_invalida', 413 if grande else 400,
                      diagnostico=_diagnostico_para(request, 'imagen', error.codigo))
    finally:
        archivo.close()

    idioma = paquete.idioma_del_visitante()
    try:
        descripcion = cliente.describir(vision.armar_solicitud(preparada, idioma))
    except coach_client.CoachNoDisponible as error:
        # La vision falla aparte: no abre el circuito del chat de texto.
        logger.warning(
            'Vendedor: el Coach no describio la foto (%s%s).',
            error.codigo, f': {error.detalle}' if error.detalle else '',
        )
        if error.reintentar_en:
            _exigir_espera(request, error.reintentar_en)
        codigo, estado_http = _ERRORES_DE_VISION.get(error.codigo, _ERROR_GENERICO_DEL_COACH)
        return _error(codigo, estado_http, error.reintentar_en,
                      diagnostico=_diagnostico_para(request, 'vision', error.codigo, error.detalle))
    except contrato.ContratoInvalido as error:
        logger.error('Vendedor: no se pudo armar la solicitud de vision (%s).', error)
        return _error('imagen_invalida', 400, diagnostico=_diagnostico_para(request, 'vision', error))
    del preparada

    if not descripcion.prenda:
        # No hay prenda que buscar: el panel lo explica sin gastar un turno.
        return JsonResponse({
            'ok': True, 'reply': '', 'notice': 'sin_prenda', 'cards': [], 'actions': [], 'handoff': None,
            'visual': {'summary': [], 'matches': 0},
        })

    coincidencias = evidencia.coincidencias_visuales(
        descripcion.atributos, linea_preferida=paquete.linea_de_ropa_preferida(request))
    return _completar_turno(
        request, cliente, texto or _mensaje_por_defecto(idioma), estado_conversacion,
        visual=paquete.bloque_visual(descripcion, coincidencias),
        extra={'visual': {
            'summary': atributos.resumen_visible(descripcion.atributos),
            'matches': len(coincidencias),
        }},
    )


@csrf_protect
def _imagen_con_csrf(request):
    return rate_limit('vendedor_imagen', settings.VENDEDOR_IMAGEN_RATE, 60)(_atender_imagen)(request)


# csrf_exempt + csrf_protect: el manejador de subida se cambia antes de que
# alguien lea request.POST (la verificacion CSRF lo lee). El token se exige igual.
@csrf_exempt
@require_POST
def imagen_vista(request):
    if not visible_para(request) or not imagen_permitida_para(request):
        raise Http404
    try:
        largo = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        largo = 0
    if largo > MAX_BYTES_PETICION_IMAGEN:
        return _error('imagen_grande', 413)
    if largo <= 0:
        return _error('imagen_invalida', 400)
    request.upload_handlers = [_SubidaEnMemoria(request)]
    return _imagen_con_csrf(request)


@require_POST
def mensaje(request):
    # Apagado o fuera del grupo expuesto: la ruta no existe, y no se cuenta
    # nada contra el limite de uso.
    if not visible_para(request):
        raise Http404
    return _limitado(_atender)(request)


@never_cache
@require_GET
def identidad_estado(request):
    """Estado opaco de la sesión para actualizar el chat sin mezclar propietarios."""
    if not visible_para(request):
        raise Http404
    result = estado.estado_usuario(request)
    response = JsonResponse(result)
    response['Cache-Control'] = 'no-store'
    return response
