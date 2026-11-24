"""Mensajes de texto al Coach y estado de la identidad de la sesion."""
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .. import contrato, estado
from ..exposicion import visible_para
from .comun import (
    _abrir_turno,
    _cliente_disponible,
    _completar_turno,
    _error,
    _leer_cuerpo,
    _limitado,
)


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
