"""Public, read-only readiness for Prime Universal Identity.

The response contains no identity attributes, tokens, credentials or internal errors.
The legacy password login remains available regardless of this endpoint.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .management.commands.oidc_preflight import (
    verificaciones_de_configuracion,
    verificar_discovery,
)


def _modo():
    if getattr(settings, 'OIDC_GLOBAL', False):
        return 'global'
    if getattr(settings, 'OIDC_CANARY', False):
        return 'canary'
    return 'disabled'


def _ready():
    # Cache by effective settings (including the secret hash, never its value),
    # so settings changes cannot reuse a prior successful probe.
    config = getattr(settings, 'GOTOGYM_OIDC', {})
    fingerprint = hashlib.sha256(repr((
        config.get('ISSUER'), config.get('DISCOVERY_URL'),
        config.get('CLIENT_ID'), config.get('CLIENT_SECRET'),
        config.get('REDIRECT_URI'), config.get('SUBJECT_CLAIM'),
        config.get('ALLOW_AUTO_CREATE'), config.get('REQUIRE_EMAIL_VERIFIED_CLAIM'),
        getattr(settings, 'OIDC_GLOBAL', False),
        getattr(settings, 'OIDC_CANARY', False),
        sorted(getattr(settings, 'OIDC_CANARY_OBJECT_IDS', ())),
    )).encode()).hexdigest()
    key = 'prime:identity:readiness:' + fingerprint
    try:
        cached = cache.get(key)
        if isinstance(cached, bool):
            return cached
    except Exception:
        pass
    try:
        checks = verificaciones_de_configuracion() + verificar_discovery()
        ready = all(item['ok'] for item in checks if item['blocking'])
    except Exception:
        # Unavailable databases/providers must not lead to enabled=true.
        ready = False
    try:
        cache.set(key, ready, 15)
    except Exception:
        pass
    return ready


@never_cache
@require_GET
def status(request):
    mode = _modo()
    ready = _ready()
    return JsonResponse({
        'enabled': mode == 'global' and ready,
        'canary': mode == 'canary' and ready,
        'ready': ready,
    })
