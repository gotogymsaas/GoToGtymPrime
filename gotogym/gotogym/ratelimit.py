"""Limitador de tasa minimo, basado en el cache de Django.

No sustituye un limitador de infraestructura real (proxy, CDN, etc.): usa el
backend de cache configurado. En produccion la cache es compartida entre los
workers (Redis, o una tabla en la base de datos; ver settings.py); solo en
desarrollo y pruebas es `LocMemCache`, por proceso. Es suficiente para
frenar el abuso trivial de un solo cliente contra un endpoint sensible; no
protege contra un ataque distribuido desde muchas IPs.
"""
import time

from django.conf import settings
from django.core.cache import DEFAULT_CACHE_ALIAS, cache, caches
from django.core.cache.backends.redis import RedisCache
from django.http import HttpResponse


def _ahora():
    return time.time()


def _clave_de_ventana(clave_base, periodo, desfase=0):
    return f'{clave_base}:{int((_ahora() + desfase) // periodo)}'


def contar(clave_base, periodo, desfase=0):
    """Suma uno al contador de la ventana actual de `periodo` segundos y
    devuelve el total de la ventana.

    El numero de ventana forma parte de la clave, asi que cada ventana empieza
    en cero por si sola y no importa si el backend renueva el vencimiento al
    escribir. Eso es lo que ocurre con la cache en tabla: su `incr` lee y
    reescribe el valor sin vencimiento propio, y la clave pasa a durar el
    valor por defecto (300 s) en vez de la ventana. Por eso solo se usa `incr`
    donde es nativo y atomico (Redis); en los demas backends se escribe con el
    vencimiento explicito. Alli el conteo no es atomico: con peticiones
    simultaneas del mismo cliente puede quedar por debajo del real, lo que es
    aceptable para frenar abuso pero no para un cupo estricto.

    Las ventanas empiezan en multiplos de `periodo` contados desde el
    meridiano de UTC. `desfase` (en segundos, sumado al reloj) las corre: una
    ventana de un dia con el desfase de la zona horaria del sitio empieza a la
    medianoche local."""
    clave = _clave_de_ventana(clave_base, periodo, desfase)
    if cache.add(clave, 1, timeout=periodo):
        return 1
    if isinstance(caches[DEFAULT_CACHE_ALIAS], RedisCache):
        try:
            return cache.incr(clave)
        except ValueError:
            pass  # caduco entre `add` e `incr`: se vuelve a crear abajo
    else:
        actual = cache.get(clave)
        if actual is not None:
            cache.set(clave, actual + 1, timeout=periodo)
            return actual + 1
    cache.set(clave, 1, timeout=periodo)
    return 1


def olvidar(clave_base, periodo, desfase=0):
    """Pone a cero el contador de la ventana actual."""
    cache.delete(_clave_de_ventana(clave_base, periodo, desfase))


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

    La ventana es fija y esta alineada al reloj (ver `contar`): no se prolonga
    con cada peticion. Es atomico solo con Redis; con la cache en tabla puede
    dejar pasar alguna peticion simultanea de mas.

    `metodos` limita el conteo a esos metodos HTTP (por ejemplo `('POST',)`
    para contar intentos de acceso y no las visitas al formulario). Con
    `RATE_LIMIT_ENABLED` en falso (pruebas) no limita nada."""
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            if not getattr(settings, 'RATE_LIMIT_ENABLED', True):
                return view_func(request, *args, **kwargs)
            if metodos and request.method not in metodos:
                return view_func(request, *args, **kwargs)
            intentos = contar(f'ratelimit:{key_prefix}:{_client_key(request)}', period_seconds)
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
