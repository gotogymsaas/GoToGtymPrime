"""Content-Security-Policy: la politica, el nonce de las plantillas y el
endpoint que recibe los reportes de violaciones.

La politica se construye a partir de lo que el sitio realmente carga (revisado
en plantillas, CSS y JS): hoy todo sale del propio origen. Los scripts y las
hojas de estilo son de `/static/`, las fuentes estan autoalojadas y todo
`fetch`/`sendBeacon` va a rutas del mismo sitio. El pago con Mercado Pago se
abre con un enlace (`<a href>`), que es una navegacion y no pasa por
`form-action` ni por `connect-src`; por eso no hay dominios de la pasarela en la
politica. Si algun dia se carga algo de fuera, hay que agregarlo aqui.
"""
import json
import logging
import re

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .ratelimit import rate_limit

logger = logging.getLogger(__name__)

MODOS = ('reportar', 'aplicar', 'apagado')
RUTA_REPORTES = '/csp-reporte/'

# Un reporte real pesa unos cientos de bytes; mas de esto no es un reporte.
MAX_BYTES_REPORTE = 8 * 1024
# Reportes por minuto y por IP. Una pagina con muchas violaciones manda varios
# de golpe, pero no cientos.
REPORTES_POR_MINUTO = 30
_LARGO_MAXIMO_REGISTRADO = 200
_DIRECTIVA_VALIDA = re.compile(r'^[a-z-]{1,40}$')


def politica(nonce):
    """Cadena de la cabecera para un nonce dado.

    `style-src` conserva 'unsafe-inline' a proposito: hay bloques `<style>` y
    atributos `style=` en plantillas de la tienda, el panel, el checkout y los
    correos, y un nonce no cubre los atributos. Quitarlo exige mover esos estilos
    a hojas estaticas; los scripts, que son lo que abre la puerta a XSS, si se
    controlan con nonce.
    """
    directivas = [
        "default-src 'self'",
        f"script-src 'self' 'nonce-{nonce}'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
        f'report-uri {RUTA_REPORTES}',
    ]
    return '; '.join(directivas)


def csp_nonce(request):
    """Procesador de contexto: expone el nonce de la peticion a las plantillas
    (`<script nonce="{{ csp_nonce }}">`). Sin el middleware (p. ej. una
    peticion armada a mano) queda vacio, y un script sin nonce solo se reporta."""
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


def _sin_consulta(valor):
    """Recorta un URI para el registro: sin query string ni fragmento (pueden
    llevar tokens o datos personales), sin caracteres de control (evita
    falsificar lineas del registro) y con largo acotado."""
    if not isinstance(valor, str):
        return ''
    valor = valor.split('?', 1)[0].split('#', 1)[0]
    return ''.join(c for c in valor if c.isprintable())[:_LARGO_MAXIMO_REGISTRADO]


def _campos_del_reporte(cuerpo):
    """(directiva, uri bloqueado, pagina) de un reporte, sea el formato clasico
    (`application/csp-report`) o el de la API de Reporting (lista de reportes)."""
    if isinstance(cuerpo, list):
        cuerpo = cuerpo[0] if cuerpo else {}
    if not isinstance(cuerpo, dict):
        return None
    datos = cuerpo.get('csp-report') or cuerpo.get('body') or {}
    if not isinstance(datos, dict):
        return None
    directiva = (
        datos.get('effective-directive') or datos.get('effectiveDirective')
        or datos.get('violated-directive') or datos.get('violatedDirective')
    )
    # El navegador manda "script-src-elem 'self' 'nonce-...'": la directiva es solo
    # la primera palabra, sin la politica (que lleva el nonce).
    directiva = str(directiva or '').split(' ', 1)[0]
    if not _DIRECTIVA_VALIDA.match(directiva):
        directiva = 'desconocida'
    bloqueado = datos.get('blocked-uri', datos.get('blockedURL', ''))
    pagina = datos.get('document-uri', datos.get('documentURL', ''))
    return directiva, _sin_consulta(bloqueado), _sin_consulta(pagina)


@csrf_exempt
@require_POST
@rate_limit('csp_reporte', limit=REPORTES_POR_MINUTO, period_seconds=60)
def reporte(request):
    """Recibe un reporte de violacion de la politica y deja una linea en el
    registro con la directiva violada, el recurso bloqueado y la pagina, ambos
    sin query string. No registra IP, agente de usuario ni ningun otro dato de
    la peticion. Sin CSRF: lo envia el navegador por su cuenta, sin el token."""
    try:
        declarado = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        declarado = 0
    if declarado > MAX_BYTES_REPORTE:
        return HttpResponse(status=413)
    crudo = request.read(MAX_BYTES_REPORTE + 1)
    if len(crudo) > MAX_BYTES_REPORTE:
        return HttpResponse(status=413)
    try:
        campos = _campos_del_reporte(json.loads(crudo))
    except ValueError:
        campos = None
    if campos is None:
        return HttpResponse(status=400)
    logger.warning('CSP violada: directiva=%s bloqueado=%s pagina=%s', *campos)
    return HttpResponse(status=204)

