import os
import urllib.parse
from datetime import timedelta
from pathlib import Path


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(',') if item.strip()]


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in ('1', 'true', 'yes', 'on')

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'change-me')
DEBUG = _as_bool(os.environ.get('DEBUG'), False)
DEFAULT_ALLOWED_HOSTS = (
    'localhost,127.0.0.1,'
    'gotogym.store,www.gotogym.store,developers.gotogym.store,'
    'api.gotogym.store,gotogym-prime.azurewebsites.net,'
    'app-gotogym-api-green-pnvfv3.azurewebsites.net'
)
ALLOWED_HOSTS = _split_csv(os.environ.get('ALLOWED_HOSTS', DEFAULT_ALLOWED_HOSTS))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'accounts',
    'blog',
    'products',
    'inventory',
    'orders',
    'payments',
    'shipping',
    'contabilidad',
    'influencer',
    'tienda',
    'carrito',
    'administracion',
    'analitica',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'gotogym.middleware.DefaultLanguageMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'influencer.middleware.ReferralTrackingMiddleware',
]

ROOT_URLCONF = 'gotogym.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'gotogym' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'carrito.context_processors.cart_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'gotogym.wsgi.application'

# Motor de base de datos, en orden de prioridad:
#
# 1. DATABASE_URL  -> PostgreSQL. Es el motor objetivo para los entornos
#    desplegados; el driver (psycopg2-binary) esta en requirements.txt.
# 2. MYSQL_*       -> MySQL. Solo para entornos heredados que aun declaren
#    esas variables de forma explicita. El driver requerido por este backend
#    (mysqlclient) NO esta en requirements.txt, asi que un entorno que caiga
#    aqui debe instalarlo aparte. No usar en entornos nuevos.
# 3. Sin variables -> SQLite local, para poder ejecutar manage.py sin
#    configuracion previa. Nunca apunta a un servidor remoto por defecto.
_db_url = os.environ.get('DATABASE_URL', '')
if _db_url:
    _p = urllib.parse.urlparse(_db_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _p.path.lstrip('/'),
            'USER': urllib.parse.unquote(_p.username or ''),
            'PASSWORD': urllib.parse.unquote(_p.password or ''),
            'HOST': _p.hostname,
            'PORT': str(_p.port or 5432),
            'OPTIONS': {'sslmode': 'require'},
        }
    }
elif os.environ.get('MYSQL_HOST') or os.environ.get('MYSQL_DATABASE'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'gotogym_bd'),
            'USER': os.environ.get('MYSQL_USER', 'gotogym_user'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
            'HOST': os.environ.get('MYSQL_HOST', ''),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(BASE_DIR / 'db.sqlite3'),
        }
    }


AUTH_PASSWORD_VALIDATORS: list[dict] = []

# Internacionalización. Import a mitad de archivo, a proposito: vive justo
# junto a lo unico que lo usa (LANGUAGES, dos lineas abajo).
from django.utils.translation import gettext_lazy as _  # noqa: E402

LANGUAGES = [
    ('es', _('Español')),
    ('en', _('English')),
    ('pt', _('Português')),
]

LANGUAGE_CODE = 'es'
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = _as_bool(os.environ.get('CORS_ALLOW_ALL_ORIGINS'), False)
DEFAULT_CORS_ALLOWED_ORIGINS = (
    'https://developers.gotogym.store,'
    'https://api.gotogym.store,'
    'https://gotogym.store,'
    'https://www.gotogym.store'
)
CORS_ALLOWED_ORIGINS = _split_csv(os.environ.get('CORS_ALLOWED_ORIGINS', DEFAULT_CORS_ALLOWED_ORIGINS))

CSRF_TRUSTED_ORIGINS = _split_csv(os.environ.get('CSRF_TRUSTED_ORIGINS', ''))

# Requerido para que Django confíe en HTTPS detrás del proxy de Azure App Service
if _as_bool(os.environ.get('SECURE_PROXY_SSL_HEADER'), False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = _as_bool(os.environ.get('SECURE_SSL_REDIRECT'), False)
SESSION_COOKIE_SECURE = _as_bool(os.environ.get('SESSION_COOKIE_SECURE'), False)
CSRF_COOKIE_SECURE = _as_bool(os.environ.get('CSRF_COOKIE_SECURE'), False)

# Panel de simulacion de pagos: visible en desarrollo (DEBUG) o si se activa
# explicitamente. Nunca debe quedar accesible en produccion real.
PAYMENTS_MOCK_UI_ENABLED = _as_bool(os.environ.get('PAYMENTS_MOCK_UI_ENABLED'), False)

# Proveedor de pago activo en el checkout. "mock" (default, en todo entorno
# que no declare esta variable) o "mercadopago". Cambiar esto no requiere
# tocar el checkout ni las vistas de payments, solo esta variable.
PAYMENT_PROVIDER = os.environ.get('PAYMENT_PROVIDER', 'mock')

# Variables críticas de integraciones para runtime.
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')
MERCADOPAGO_WEBHOOK_SECRET = os.environ.get('MERCADOPAGO_WEBHOOK_SECRET', '')
HUBSPOT_PRIVATE_TOKEN = os.environ.get('HUBSPOT_PRIVATE_TOKEN', '')
# Compatibilidad: prioriza ALEGRA_API_TOKEN y usa ALEGRA_TOKEN como fallback.
ALEGRA_API_TOKEN = os.environ.get('ALEGRA_API_TOKEN') or os.environ.get('ALEGRA_TOKEN', '')

# Monitoreo de errores (Sentry). Sin SENTRY_DSN en el entorno queda
# desactivado: no requiere la librería instalada para arrancar y no rompe
# entornos (local, tests) que no lo configuren.
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.2')),
        send_default_pii=False,
    )

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
}

AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'commercial_login'
LOGIN_REDIRECT_URL = 'home'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Envío de correo (recuperación de contraseña, notificaciones transaccionales).
# Sin EMAIL_HOST en el entorno, cae a console backend para no romper en un
# despliegue que aún no tenga el proveedor SMTP configurado.
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = _as_bool(os.environ.get('EMAIL_USE_TLS'), True)
    EMAIL_USE_SSL = _as_bool(os.environ.get('EMAIL_USE_SSL'), False)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'GoToGym <no-reply@gotogym.store>')
