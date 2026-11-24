"""Busqueda por foto: la imagen se describe con el modelo de vision y la
descripcion alimenta un turno normal del Coach."""
import logging

from django.conf import settings
from django.http import Http404, JsonResponse
from django.utils import timezone, translation
from django.utils.translation import gettext
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
from gotogym.ratelimit import contar, rate_limit
from products import atributos

from .. import coach_client, contrato, evidencia, imagen, paquete, vision
from ..exposicion import imagen_permitida_para, visible_para
from .comun import (
    _ERROR_GENERICO_DEL_COACH,
    SEGUNDOS_DIA,
    _abrir_turno,
    _clave_de_cliente,
    _cliente_disponible,
    _completar_turno,
    _diagnostico_para,
    _error,
    _exigir_espera,
    _largo_declarado,
    _SubidaEnMemoria,
)

# Nombre fijo (el del modulo que antes lo contenia todo): es el que los
# filtros de registro y las alertas ya conocen.
logger = logging.getLogger('vendedor.views')


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
    largo = _largo_declarado(request)
    if largo > MAX_BYTES_PETICION_IMAGEN:
        return _error('imagen_grande', 413)
    if largo <= 0:
        return _error('imagen_invalida', 400)
    request.upload_handlers = [_SubidaEnMemoria(request, MAX_BYTES_PETICION_IMAGEN)]
    return _imagen_con_csrf(request)
