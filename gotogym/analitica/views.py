"""Recepcion de eventos de uso del sitio.

Es analitica de primera parte: los eventos se guardan en la base del
proyecto y no salen hacia ningun tercero, asi que no hay script externo
que cargar ni identificadores publicitarios que pedir. A cambio, la vista
tiene que defenderse sola, porque el cliente que la llama es el navegador
de cualquiera.

Tres defensas, en este orden:

1. `EVENTOS_PERMITIDOS` - solo se aceptan nombres conocidos. Sin esto la
   tabla se llena de nombres arbitrarios y deja de poder agregarse.
2. `_limpiar_propiedades` - recorta claves, longitud y tipo. Evita tanto
   el abuso como el accidente de que alguien mande un correo o un token
   dentro de un evento.
3. Limite de tasa y de tamano del lote.
"""
import hashlib
import json

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from gotogym.ratelimit import rate_limit

from .models import EventoAnalitica

# Taxonomia cerrada. Al anadir un evento nuevo en una plantilla hay que
# declararlo aqui tambien, o la vista lo descarta en silencio.
EVENTOS_PERMITIDOS = frozenset({
    'page_view',
    'hero_collection',
    'hero_technology',
    'intent_performance',
    'intent_daily',
    'intent_custom',
    'featured_product',
    'product_impression',
    'product_click',
    'add_to_cart',
    'search_submit',
})

MAX_EVENTOS_POR_LOTE = 40
MAX_PROPIEDADES = 8
MAX_LARGO_VALOR = 120


def _hash_sesion(request):
    """Identificador estable por sesion que no permite recuperar la clave.

    Se siembra con SECRET_KEY para que el hash no sea reversible por fuerza
    bruta sobre el espacio de claves de sesion.
    """
    clave = request.session.session_key
    if not clave:
        return ''
    from django.conf import settings
    semilla = f'{settings.SECRET_KEY}:{clave}'.encode()
    return hashlib.sha256(semilla).hexdigest()[:32]


def _limpiar_propiedades(crudas):
    if not isinstance(crudas, dict):
        return {}
    limpias = {}
    for clave, valor in list(crudas.items())[:MAX_PROPIEDADES]:
        if not isinstance(clave, str):
            continue
        clave = clave[:40]
        if isinstance(valor, bool) or isinstance(valor, int):
            limpias[clave] = valor
        elif isinstance(valor, float):
            limpias[clave] = round(valor, 4)
        elif isinstance(valor, str):
            limpias[clave] = valor[:MAX_LARGO_VALOR]
        # Cualquier otro tipo (listas, dicts anidados) se descarta: no hay
        # ninguna pregunta de producto que hoy los necesite y son la via
        # facil para colar una carga grande.
    return limpias


@require_POST
@rate_limit('analitica_eventos', limit=60, period_seconds=60)
def registrar_eventos(request):
    """Recibe un lote de eventos enviado con sendBeacon.

    El cuerpo llega como multipart porque sendBeacon no puede fijar
    cabeceras propias: mandar un FormData es lo que permite incluir el
    token CSRF y que la proteccion siga activa.
    """
    try:
        lote = json.loads(request.POST.get('eventos', '[]'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'json invalido'}, status=400)

    if not isinstance(lote, list):
        return JsonResponse({'ok': False, 'error': 'se esperaba una lista'}, status=400)

    autenticado = request.user.is_authenticated
    sesion = _hash_sesion(request)

    filas = []
    for crudo in lote[:MAX_EVENTOS_POR_LOTE]:
        if not isinstance(crudo, dict):
            continue
        nombre = crudo.get('nombre')
        if nombre not in EVENTOS_PERMITIDOS:
            continue
        filas.append(EventoAnalitica(
            nombre=nombre,
            ruta=str(crudo.get('ruta', ''))[:300],
            sesion=sesion,
            autenticado=autenticado,
            propiedades=_limpiar_propiedades(crudo.get('propiedades')),
        ))

    if filas:
        with transaction.atomic():
            EventoAnalitica.objects.bulk_create(filas)

    return JsonResponse({'ok': True, 'guardados': len(filas)})
