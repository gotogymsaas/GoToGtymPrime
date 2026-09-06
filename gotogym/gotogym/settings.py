import os
import sys
import urllib.parse
from pathlib import Path
from datetime import timedelta


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(',') if item.strip()]


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in ('1', 'true', 'yes', 'on')

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
ADMIN_PROJECT_DIR = PROJECT_ROOT / 'GoToGymAdmin'

if ADMIN_PROJECT_DIR.exists() and str(ADMIN_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_PROJECT_DIR))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'change-me')
DEBUG = _as_bool(os.environ.get('DEBUG'), False)
ALLOWED_HOSTS = _split_csv(os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1'))

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
    'configuracion_marca',
    'contabilidad',
    'influencer',
    'tienda',
    'carrito',
    'crm',
    'metricas',
    'administracion',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gotogym.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'gotogym' / 'templates',
            ADMIN_PROJECT_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gotogym.wsgi.application'

#DATABASES = {
#    'default': {
#        'ENGINE': 'django.db.backends.postgresql',
#        'NAME': os.environ.get('POSTGRES_DB', 'gotogym'),
#        'USER': os.environ.get('POSTGRES_USER', 'gotogym'),
#        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'gotogym'),
#        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
#        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
#    }
#}


# SE ADICIONA ESTAS LINEAS PARA SABER QUE SE USA MYSQL ALVARO URREGO VIANA 05/08/2025
# DATABASE_URL tiene prioridad (PostgreSQL Azure), fallback a MYSQL_* vars
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
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'gotogym_bd'),
            'USER': os.environ.get('MYSQL_USER', 'gotogym_user'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
            'HOST': os.environ.get('MYSQL_HOST', 'servergotogym.mysql.database.azure.com'),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
        }
    }


AUTH_PASSWORD_VALIDATORS = []

# Internacionalización
from django.utils.translation import gettext_lazy as _

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
    ADMIN_PROJECT_DIR / 'static',
]
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = _as_bool(os.environ.get('CORS_ALLOW_ALL_ORIGINS'), False)
CORS_ALLOWED_ORIGINS = _split_csv(os.environ.get('CORS_ALLOWED_ORIGINS', ''))

CSRF_TRUSTED_ORIGINS = _split_csv(os.environ.get('CSRF_TRUSTED_ORIGINS', ''))

# Requerido para que Django confíe en HTTPS detrás del proxy de Azure App Service
if _as_bool(os.environ.get('SECURE_PROXY_SSL_HEADER'), False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = _as_bool(os.environ.get('SECURE_SSL_REDIRECT'), False)
SESSION_COOKIE_SECURE = _as_bool(os.environ.get('SESSION_COOKIE_SECURE'), False)
CSRF_COOKIE_SECURE = _as_bool(os.environ.get('CSRF_COOKIE_SECURE'), False)

# Variables críticas de integraciones para runtime.
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')
HUBSPOT_PRIVATE_TOKEN = os.environ.get('HUBSPOT_PRIVATE_TOKEN', '')
# Compatibilidad: prioriza ALEGRA_API_TOKEN y usa ALEGRA_TOKEN como fallback.
ALEGRA_API_TOKEN = os.environ.get('ALEGRA_API_TOKEN') or os.environ.get('ALEGRA_TOKEN', '')

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
LOGIN_REDIRECT_URL = 'logged_home'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
