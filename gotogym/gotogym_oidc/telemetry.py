"""Bounded aggregate counters and structured audit. No tokens, emails or claims."""
import logging
import time

from django.core.cache import cache

logger = logging.getLogger('gotogym_oidc.audit')


_SEGUNDOS_DIA = 86400


def _sumar_al_dia(clave):
    """Suma uno al contador del dia en curso. La fecha va en la clave y el
    vencimiento se escribe de forma explicita: `incr` de la cache en tabla
    reescribe la clave con el vencimiento por defecto (300 s) y el contador
    del dia se perderia a los pocos minutos. No es atomico en esa cache; para
    una metrica agregada no hace falta."""
    clave = f'{clave}:{int(time.time() // _SEGUNDOS_DIA)}'
    if cache.add(clave, 1, _SEGUNDOS_DIA):
        return
    cache.set(clave, (cache.get(clave) or 0) + 1, _SEGUNDOS_DIA)


def record(event, outcome):
    if event not in {'authentication', 'exchange', 'logout'} or outcome not in {'success', 'failure'}:
        raise ValueError('Invalid identity metric label')
    logger.info('identity_event', extra={'identity_event': event, 'outcome': outcome})
    key = f'gotogym_oidc:metrics:{event}:{outcome}'
    try:
        _sumar_al_dia(key)
    except Exception:
        # Cache instrumentation must not become a second authentication dependency.
        logger.warning('identity_metrics_unavailable')
