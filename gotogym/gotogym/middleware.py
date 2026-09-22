from django.conf import settings


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
