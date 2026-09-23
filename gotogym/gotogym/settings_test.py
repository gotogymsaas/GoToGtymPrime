from .settings import *

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

ROOT_URLCONF = 'gotogym.urls'
WSGI_APPLICATION = 'gotogym.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (),
    'DEFAULT_PERMISSION_CLASSES': (),
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# En produccion los estaticos llevan hash de contenido
# (CompressedManifestStaticFilesStorage), pero ese backend resuelve cada
# {% static %} contra staticfiles.json, que solo existe despues de
# collectstatic. La suite corre antes de ese paso en CI, y ademas no tiene
# nada que verificar sobre el hashing: se queda con el backend simple para
# no depender de un artefacto de build.
STORAGES = {
    **STORAGES,
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

AUTH_USER_MODEL = 'accounts.User'

ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
