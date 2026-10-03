"""Limitador de tasa minimo, basado en el cache de Django.

No sustituye un limitador de infraestructura real (proxy, CDN, etc.): usa el
backend de cache configurado (`LocMemCache` por defecto, que es por proceso,
no compartido entre workers de un mismo despliegue). Es suficiente para
frenar el abuso trivial de un solo cliente contra un endpoint sensible; no
protege contra un ataque distribuido desde muchas IPs.
"""
from django.core.cache import cache
from django.http import HttpResponse


def _client_key(request):
    if request.user.is_authenticated:
        return f'user:{request.user.pk}'
    return f'ip:{request.META.get("REMOTE_ADDR", "unknown")}'


def rate_limit(key_prefix, limit, period_seconds):
    """Permite como maximo `limit` peticiones por ventana de `period_seconds`,
    por usuario autenticado o por IP si es anonimo. Al superarse, responde 429
    sin ejecutar la vista.

    El contador es atomico (`add` + `incr`): con una cache compartida entre
    procesos, leer y luego escribir dejaria pasar peticiones simultaneas de
    mas. La ventana es fija: empieza con la primera peticion y no se prolonga
    con las siguientes."""
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
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
