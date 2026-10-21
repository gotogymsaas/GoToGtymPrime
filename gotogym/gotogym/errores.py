"""Paginas de error por codigo de estado.

Cada codigo tiene su pagina con el mismo diseno del sitio. El registro en
`logs/errores.txt` no se hace aqui sino en `django.request` (ver
registro_errores.py), que ya loguea toda respuesta 4xx/5xx; estas vistas solo
muestran la pagina y la referencia que quedo escrita en el log.
"""
import logging

from django.conf import settings
from django.http import HttpResponse
from django.template import loader
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import requires_csrf_token

from .registro_errores import referencia_de

logger = logging.getLogger(__name__)

# codigo -> (titulo, mensaje)
PAGINAS = {
    400: (
        _('Solicitud no válida'),
        _('No pudimos entender lo que se envió. Revisa los datos e inténtalo de nuevo.'),
    ),
    403: (
        _('Acceso denegado'),
        _('No tienes permiso para ver esta página. Si crees que es un error, escríbenos.'),
    ),
    404: (
        _('Página no encontrada'),
        _('La dirección que buscas no existe o fue movida.'),
    ),
    405: (
        _('Acción no permitida'),
        _('Esta página no admite la acción que intentaste realizar.'),
    ),
    429: (
        _('Demasiadas solicitudes'),
        _('Hiciste muchas solicitudes seguidas. Espera unos segundos e inténtalo de nuevo.'),
    ),
    500: (
        _('Algo salió mal'),
        _('Tuvimos un problema de nuestro lado. Ya quedó registrado y lo revisaremos.'),
    ),
}
CODIGOS_CON_PAGINA = frozenset(PAGINAS)


def pagina_de_error(request, codigo):
    """Respuesta HTML para `codigo` con el diseno del sitio. Si renderizar la
    plantilla completa falla (base de datos caida, contexto roto), cae en la
    pagina autonoma de `500.html`, que no depende de nada del sitio."""
    titulo, mensaje = PAGINAS[codigo]
    contexto = {'codigo': codigo, 'titulo': titulo, 'mensaje': mensaje, 'referencia': referencia_de(request)}
    try:
        plantilla = loader.get_template('errores/pagina_error.html')
        return HttpResponse(plantilla.render(contexto, request), status=codigo)
    except Exception:
        logger.exception('No se pudo renderizar la pagina de error %s; se usa la autonoma.', codigo)
        return _pagina_autonoma(request, codigo)


def _pagina_autonoma(request, codigo):
    titulo, mensaje = PAGINAS[codigo]
    contexto = {'codigo': codigo, 'titulo': titulo, 'mensaje': mensaje, 'referencia': referencia_de(request)}
    return HttpResponse(loader.render_to_string('errores/500.html', contexto), status=codigo)


@requires_csrf_token
def error_400(request, exception=None):
    return pagina_de_error(request, 400)


@requires_csrf_token
def error_403(request, exception=None):
    return pagina_de_error(request, 403)


@requires_csrf_token
def error_404(request, exception=None):
    return pagina_de_error(request, 404)


@requires_csrf_token
def error_500(request):
    # Sin contexto de plantilla: si lo que fallo es la base de datos o un
    # procesador de contexto, la pagina completa volveria a fallar.
    return _pagina_autonoma(request, 500)


def fallo_csrf(request, reason=''):
    """Token CSRF ausente o invalido (formulario viejo, cookies bloqueadas).
    El motivo ya lo registra `django.security.csrf` antes de llegar aqui."""
    return pagina_de_error(request, 403)


class PaginaDeErrorMiddleware:
    """Cambia las respuestas 405 y 429 en bruto por su pagina de error.

    Django no tiene un handler para ellas: un 405 sale con el cuerpo vacio y
    el limitador de tasa responde con una linea de texto. Se respetan las
    peticiones que esperan JSON (AJAX, webhooks), que deben conservar su
    respuesta original. Va al final de MIDDLEWARE para que la pagina se
    renderice con sesion y usuario ya resueltos.

    Con `REEMPLAZAR_PAGINAS_DE_DEBUG` (solo en settings_local) tambien cambia
    los 404 y 500 de la pagina tecnica de Django por las del sitio. Con DEBUG
    activo Django ignora handler404/handler500, asi que en desarrollo nunca se
    veria el diseno real. El traceback sigue en la consola y en el log."""

    CODIGOS = (405, 429)
    CODIGOS_DE_DEBUG = (404, 500)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        codigos = self.CODIGOS
        if settings.DEBUG and getattr(settings, 'REEMPLAZAR_PAGINAS_DE_DEBUG', False):
            codigos += self.CODIGOS_DE_DEBUG
        if respuesta.status_code in codigos and self._espera_html(request, respuesta):
            if respuesta.status_code == 500:
                # Igual que en produccion: pagina autonoma, sin plantilla del sitio.
                return _pagina_autonoma(request, 500)
            nueva = pagina_de_error(request, respuesta.status_code)
            for cabecera in ('Allow', 'Retry-After'):
                if cabecera in respuesta:
                    nueva[cabecera] = respuesta[cabecera]
            return nueva
        return respuesta

    @staticmethod
    def _espera_html(request, respuesta):
        if request.path.startswith('/pagos/webhook/'):
            return False
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return False
        if 'application/json' in request.headers.get('accept', ''):
            return False
        return respuesta.get('Content-Type', 'text/html').startswith('text/html')
