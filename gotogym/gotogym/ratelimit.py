"""Limitador de tasa minimo, basado en el cache de Django.

No sustituye un limitador de infraestructura real (proxy, CDN, etc.): usa el
backend de cache configurado. En produccion la cache es compartida entre los
workers (Redis, o una tabla en la base de datos; ver settings.py); solo en
desarrollo y pruebas es `LocMemCache`, por proceso. Es suficiente para
frenar el abuso trivial de un solo cliente contra un endpoint sensible; no
protege contra un ataque distribuido desde muchas IPs.
"""
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


def _quitar_puerto(direccion):
    """'1.2.3.4:5678' -> '1.2.3.4'; '[::1]:80' -> '::1'. Azure App Service
    agrega el puerto de origen a la IP del cliente."""
    if direccion.startswith('[') and ']' in direccion:
        return direccion[1:direccion.index(']')]
    if direccion.count(':') == 1:
        return direccion.split(':', 1)[0]
    return direccion


def ip_del_cliente(request):
    """IP real del cliente.

    Detras de `TRUSTED_PROXY_HOPS` proxies de confianza, la IP del cliente es
    la que el ultimo de ellos agrego a `X-Forwarded-For`; las anteriores las
    puede inventar el propio cliente y no se usan. Sin proxies configurados
    se usa la conexion directa."""
    saltos = getattr(settings, 'TRUSTED_PROXY_HOPS', 0)
    reenviadas = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if saltos > 0 and reenviadas:
        entradas = [e.strip() for e in reenviadas.split(',') if e.strip()]
        if len(entradas) >= saltos:
            return _quitar_puerto(entradas[-saltos])
    return request.META.get('REMOTE_ADDR', 'unknown')


def _client_key(request):
    if request.user.is_authenticated:
        return f'user:{request.user.pk}'
    return f'ip:{ip_del_cliente(request)}'


def rate_limit(key_prefix, limit, period_seconds, metodos=None):
    """Permite como maximo `limit` peticiones por ventana de `period_seconds`,
    por usuario autenticado o por IP si es anonimo. Al superarse, responde 429
    sin ejecutar la vista.

    El contador es atomico (`add` + `incr`): con una cache compartida entre
    procesos, leer y luego escribir dejaria pasar peticiones simultaneas de
    mas. La ventana es fija: empieza con la primera peticion y no se prolonga
    con las siguientes.

    `metodos` limita el conteo a esos metodos HTTP (por ejemplo `('POST',)`
    para contar intentos de acceso y no las visitas al formulario). Con
    `RATE_LIMIT_ENABLED` en falso (pruebas) no limita nada."""
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            if not getattr(settings, 'RATE_LIMIT_ENABLED', True):
                return view_func(request, *args, **kwargs)
            if metodos and request.method not in metodos:
                return view_func(request, *args, **kwargs)
            cache_key = f'ratelimit:{key_prefix}:{_client_key(request)}'
            cache.add(cache_key, 0, timeout=period_seconds)
            try:
                intentos = cache.incr(cache_key)
            except ValueError:
                # La clave caduco entre `add` e `incr`: empieza otra ventana.
                cache.set(cache_key, 1, timeout=period_seconds)
                intentos = 1
            if intentos > limit:
                return HttpResponse(
                    'Demasiadas solicitudes. Intenta de nuevo en unos segundos.',
                    status=429,
                )
            return view_func(request, *args, **kwargs)
        wrapped.__name__ = getattr(view_func, '__name__', 'wrapped')
        wrapped.__doc__ = view_func.__doc__
        return wrapped
    return decorator
