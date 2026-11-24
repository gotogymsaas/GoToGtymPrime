"""Archivo adjunto: el texto del documento viaja al Coach como un turno."""
from django.http import Http404
from django.utils import translation
from django.utils.translation import gettext
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
from gotogym.ratelimit import rate_limit

from .. import contrato, documento, paquete
from ..exposicion import visible_para
from .comun import (
    _abrir_turno,
    _cliente_disponible,
    _completar_turno,
    _diagnostico_para,
    _error,
    _largo_declarado,
    _SubidaEnMemoria,
)

MAX_BYTES_PETICION_DOCUMENTO = documento.MAX_BYTES_SUBIDA + 64 * 1024
# Archivos por minuto y por persona. Cada uno es un turno normal (cuenta contra
# el tope diario de mensajes); este tope frena el envio en rafaga.
DOCUMENTOS_POR_MINUTO = 3

_ERRORES_DE_DOCUMENTO = {
    'grande': ('documento_grande', 413),
    'sin_texto': ('documento_sin_texto', 422),
    'protegido': ('documento_protegido', 422),
}


def _mensaje_de_documento(idioma):
    with translation.override(idioma):
        return gettext('Te comparto un archivo para que me ayudes con mi compra.')


def _atender_documento(request):
    if request.content_type != 'multipart/form-data':
        return _error('documento_invalido', 415)
    archivo = request.FILES.get('documento')
    if archivo is None:
        return _error('documento_invalido', 400)
    texto = (request.POST.get('message') or '').strip()
    if len(texto) > contrato.MAX_LARGO_MENSAJE:
        return _error('mensaje_invalido', 400)

    cliente, fallo = _cliente_disponible(request)
    if fallo:
        return fallo
    estado_conversacion, fallo = _abrir_turno(request, reiniciar=request.POST.get('new') == '1')
    if fallo:
        return fallo
    try:
        leido = documento.leer(archivo.read(), archivo.name or '')
    except documento.DocumentoInvalido as error:
        codigo, estado_http = _ERRORES_DE_DOCUMENTO.get(error.codigo, ('documento_invalido', 400))
        return _error(codigo, estado_http, diagnostico=_diagnostico_para(request, 'documento', error.codigo))
    finally:
        archivo.close()

    idioma = paquete.idioma_del_visitante()
    return _completar_turno(
        request, cliente, texto or _mensaje_de_documento(idioma), estado_conversacion,
        adjunto=paquete.bloque_adjunto(leido),
        extra={'document': {'format': leido.formato, 'truncated': leido.recortado}},
    )


@csrf_protect
def _documento_con_csrf(request):
    return rate_limit('vendedor_documento', DOCUMENTOS_POR_MINUTO, 60)(_atender_documento)(request)


@csrf_exempt
@require_POST
def documento_vista(request):
    if not visible_para(request):
        raise Http404
    largo = _largo_declarado(request)
    if largo > MAX_BYTES_PETICION_DOCUMENTO:
        return _error('documento_grande', 413)
    if largo <= 0:
        return _error('documento_invalido', 400)
    request.upload_handlers = [_SubidaEnMemoria(request, MAX_BYTES_PETICION_DOCUMENTO)]
    return _documento_con_csrf(request)
