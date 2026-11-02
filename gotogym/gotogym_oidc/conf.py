"""Lectura de la configuracion `GOTOGYM_OIDC` de settings.py.

Se lee en cada llamada (no al importar) para que `override_settings` funcione
en las pruebas y para fallar con un mensaje claro si falta algo obligatorio.
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

REQUIRED = ('ISSUER', 'CLIENT_ID')

DEFAULTS = {
    'ENABLED': True,
    # Emisor exacto de los tokens. Se compara tal cual con el `issuer` del
    # documento de discovery y con el claim `iss` de cada ID token.
    'ISSUER': None,
    # Si el discovery no esta en <ISSUER>/.well-known/openid-configuration.
    'DISCOVERY_URL': None,
    'CLIENT_ID': None,
    # Vacio solo si el cliente se registra como publico (PKCE sin secreto).
    'CLIENT_SECRET': '',
    'REQUIRE_CLIENT_SECRET': False,
    'SCOPES': 'openid profile email',
    # URL absoluta registrada en el IdP. Si falta se arma con la peticion.
    'REDIRECT_URI': None,
    # Claim que identifica a la persona de forma estable. En Entra External
    # ID `sub` cambia por aplicacion: usar 'oid'.
    'SUBJECT_CLAIM': 'sub',
    'ID_TOKEN_ALGORITHMS': ['RS256'],
    'CLOCK_SKEW_SECONDS': 60,
    'HTTP_TIMEOUT_SECONDS': 5,
    'METADATA_TTL_SECONDS': 3600,
    # Cuanto puede tardar la persona en volver del IdP.
    'FLOW_TTL_SECONDS': 600,
    'ALLOW_AUTO_CREATE': True,
    # Si el IdP emite `email_verified` y es falso, se rechaza siempre. Con
    # True tambien se rechaza cuando el claim no viene.
    'REQUIRE_EMAIL_VERIFIED_CLAIM': False,
    'LINK_MAX_ATTEMPTS': 5,
    'LINK_ATTEMPTS_WINDOW_SECONDS': 900,
    'ADAPTER': 'gotogym_oidc.adapter.DefaultAdapter',
    'AUTH_BACKEND': 'django.contrib.auth.backends.ModelBackend',
    # A donde ir si el flujo falla (por defecto settings.LOGIN_URL).
    'ERROR_REDIRECT_URL': None,
    # A donde vuelve el IdP tras cerrar sesion (debe estar registrada alla).
    'POST_LOGOUT_REDIRECT_URI': None,
}


def get(name):
    user_conf = getattr(settings, 'GOTOGYM_OIDC', None)
    if not isinstance(user_conf, dict):
        raise ImproperlyConfigured('Falta el diccionario GOTOGYM_OIDC en settings.')
    if name not in DEFAULTS:
        raise KeyError(name)
    value = user_conf.get(name, DEFAULTS[name])
    if name in REQUIRED and not value:
        raise ImproperlyConfigured(f'GOTOGYM_OIDC["{name}"] es obligatorio.')
    return value


