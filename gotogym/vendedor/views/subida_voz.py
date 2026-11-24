"""Dictado por voz (respaldo del dictado del navegador)."""
import logging

from django.conf import settings
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
from gotogym.ratelimit import contar, rate_limit

from .. import coach_client, contrato, paquete, voz
from ..exposicion import visible_para
from .comun import (
    _ERROR_GENERICO_DEL_COACH,
    SEGUNDOS_DIA,
    _clave_de_cliente,
    _cliente_disponible,
    _diagnostico_para,
    _error,
    _exigir_espera,
    _largo_declarado,
    _segundos_de_espera,
    _SubidaEnMemoria,
)

# Nombre fijo (el del modulo que antes lo contenia todo): es el que los
# filtros de registro y las alertas ya conocen.
logger = logging.getLogger('vendedor.views')


MAX_BYTES_PETICION_VOZ = voz.MAX_BYTES_SUBIDA + 16 * 1024
# Notas de voz por minuto y por persona, por persona y dia, y en toda la tienda
# por dia (tope de costo del reconocimiento de voz).
VOZ_POR_MINUTO = 6
VOZ_MAX_DIA = 40
VOZ_MAX_DIA_GLOBAL = 1500

_ERRORES_DE_VOZ = {
    'no_soportado': ('voz_no_disponible', 503),
    'no_configurado': ('voz_no_disponible', 503),
    'timeout': ('timeout', 504),
    'limite': ('espera', 429),
    'error_del_coach': ('voz_no_disponible', 503),
}


def _tope_de_voz_superado(request):
    if not getattr(settings, 'RATE_LIMIT_ENABLED', True):
        return False
    desfase = int(timezone.localtime().utcoffset().total_seconds())
    if contar(f'vendedor:voz:dia:{_clave_de_cliente(request)}', SEGUNDOS_DIA, desfase) > VOZ_MAX_DIA:
        return True
    return contar('vendedor:voz:dia:global', SEGUNDOS_DIA, desfase) > VOZ_MAX_DIA_GLOBAL


def _atender_voz(request):
    if request.content_type != 'multipart/form-data':
        return _error('voz_invalida', 415)
    archivo = request.FILES.get('audio')
    if archivo is None:
        return _error('voz_invalida', 400)
    cliente, fallo = _cliente_disponible(request)
    if fallo:
        return fallo
    espera = _segundos_de_espera(request)
    if espera:
        return _error('espera', 429, espera)
    if _tope_de_voz_superado(request):
        return _error('limite_voz', 429)
    try:
        preparado = voz.preparar(archivo.read())
    except voz.VozInvalida as error:
        larga = error.codigo in ('larga', 'grande')
        return _error('voz_larga' if larga else 'voz_invalida', 413 if larga else 400,
                      diagnostico=_diagnostico_para(request, 'voz', error.codigo))
    finally:
        archivo.close()

    try:
        transcripcion = cliente.transcribir(
            voz.armar_solicitud(preparado, paquete.idioma_del_visitante(), request.POST.get('region', '')))
    except coach_client.CoachNoDisponible as error:
        logger.warning(
            'Vendedor: el Coach no transcribio la nota de voz (%s%s).',
            error.codigo, f': {error.detalle}' if error.detalle else '',
        )
        if error.reintentar_en:
            _exigir_espera(request, error.reintentar_en)
        codigo, estado_http = _ERRORES_DE_VOZ.get(error.codigo, _ERROR_GENERICO_DEL_COACH)
        return _error(codigo, estado_http, error.reintentar_en,
                      diagnostico=_diagnostico_para(request, 'voz', error.codigo, error.detalle))
    except contrato.ContratoInvalido as error:
        logger.error('Vendedor: no se pudo armar la solicitud de voz (%s).', error)
        return _error('voz_invalida', 400, diagnostico=_diagnostico_para(request, 'voz', error))
    del preparado
    return JsonResponse({'ok': True, 'text': transcripcion.texto})


@csrf_protect
def _voz_con_csrf(request):
    return rate_limit('vendedor_voz', VOZ_POR_MINUTO, 60)(_atender_voz)(request)


@csrf_exempt
@require_POST
def voz_vista(request):
    if not visible_para(request):
        raise Http404
    largo = _largo_declarado(request)
    if largo > MAX_BYTES_PETICION_VOZ:
        return _error('voz_larga', 413)
    if largo <= 0:
        return _error('voz_invalida', 400)
    request.upload_handlers = [_SubidaEnMemoria(request, MAX_BYTES_PETICION_VOZ)]
    return _voz_con_csrf(request)
