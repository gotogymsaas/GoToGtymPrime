"""Bounded aggregate counters and structured audit. No tokens, emails or claims."""
import logging

from django.core.cache import cache

logger = logging.getLogger('gotogym_oidc.audit')


def record(event, outcome):
    if event not in {'authentication', 'exchange', 'logout'} or outcome not in {'success', 'failure'}:
        raise ValueError('Invalid identity metric label')
    logger.info('identity_event', extra={'identity_event': event, 'outcome': outcome})
    key = f'gotogym_oidc:metrics:{event}:{outcome}'
    try:
        cache.add(key, 0, 86400)
        cache.incr(key)
    except Exception:
        # Cache instrumentation must not become a second authentication dependency.
        logger.warning('identity_metrics_unavailable')
