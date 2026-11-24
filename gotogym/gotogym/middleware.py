import secrets

from django.conf import settings

from .csp import politica


class DefaultLanguageMiddleware:
    """Hace que el idioma por defecto sea el del sitio, no el del navegador.

    LocaleMiddleware resuelve el idioma en este orden: prefijo de la URL,
    sesion, cookie, cabecera Accept-Language y por ultimo LANGUAGE_CODE. Con
    un navegador en ingles la cabecera gana y un visitante nuevo aterriza en
    /en/ aunque el sitio sea en espanol.

    Este middleware retira esa cabecera cuando el visitante todavia no eligio
    idioma, de modo que la cadena caiga en LANGUAGE_CODE. Una eleccion
    explicita (URL con prefijo, selector de idioma que guarda sesion/cookie)
    se sigue respetando porque tiene prioridad sobre la cabecera.

    Debe ir antes de LocaleMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        eligio_idioma = (
            request.session.get(settings.LANGUAGE_COOKIE_NAME)
            or request.session.get('_language')
            or request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        )
        if not eligio_idioma:
            request.META.pop('HTTP_ACCEPT_LANGUAGE', None)
        return self.get_response(request)


class CSPMiddleware:
    """Pone la cabecera Content-Security-Policy segun `settings.CSP_MODO`:

    - `reportar` (por defecto): `Content-Security-Policy-Report-Only`. El
      navegador no bloquea nada y avisa a `/csp-reporte/` de cada violacion;
      sirve para afinar la politica sin romper paginas.
    - `aplicar`: `Content-Security-Policy`, el navegador bloquea.
    - `apagado`: sin cabecera.

    Genera un nonce por peticion (`request.csp_nonce`, tambien en las
    plantillas como `csp_nonce`) que autoriza los `<script>` en linea. El nonce
    se crea siempre, tambien apagado, para que las plantillas se rendericen igual.
    El modo se lee en cada peticion, no al arrancar.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        respuesta = self.get_response(request)
        modo = getattr(settings, 'CSP_MODO', 'reportar')
        if modo == 'apagado':
            return respuesta
        cabecera = 'Content-Security-Policy' if modo == 'aplicar' else 'Content-Security-Policy-Report-Only'
        # Una vista que ya fijo su propia politica (p. ej. una pagina con
        # requisitos distintos) se respeta.
        if cabecera not in respuesta:
            respuesta[cabecera] = politica(request.csp_nonce)
        return respuesta
