"""Traspaso a una persona desde el panel de Quantum Coach (agente 7).

El navegador envia el formulario; Prime crea la solicitud y asigna el
radicado. El panel solo muestra un radicado que vino en una respuesta 201 de
este endpoint: el modelo de IA nunca lo genera ni lo anuncia.
"""
import json

from atencion.forms import SolicitudForm
from atencion.models import SolicitudAtencion
from atencion.services import crear_solicitud
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from gotogym.ratelimit import rate_limit

MAX_BODY = 4096


def _enmascarar(email):
    usuario, _, dominio = email.partition('@')
    return f'{usuario[:2]}***@{dominio}' if dominio else '***'


@never_cache
@csrf_protect
@require_POST
@rate_limit('vendedor-atencion', 5, 3600, metodos=('POST',))
def solicitar(request):
    if len(request.body) > MAX_BODY or request.content_type != 'application/json':
        return JsonResponse({'error': 'invalid_request'}, status=400)
    try:
        datos = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid_request'}, status=400)
    if not isinstance(datos, dict):
        return JsonResponse({'error': 'invalid_request'}, status=400)
    form = SolicitudForm({
        'nombre': datos.get('nombre'), 'email': datos.get('email'), 'motivo': datos.get('motivo'),
        'mensaje': datos.get('mensaje'), 'acepta_contacto': datos.get('acepta_contacto') is True,
    })
    if not form.is_valid():
        return JsonResponse({'error': 'invalid_fields', 'fields': sorted(form.errors)}, status=400)
    solicitud = crear_solicitud(
        **form.cleaned_data, origen=SolicitudAtencion.Origen.QUANTUM_COACH, user=request.user,
    )
    return JsonResponse({
        'radicado': solicitud.radicado,
        'email': _enmascarar(solicitud.email),
        'correo_enviado': solicitud.correo_cliente_enviado,
    }, status=201)
