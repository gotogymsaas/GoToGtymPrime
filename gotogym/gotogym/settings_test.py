from .settings import *

# INSTALLED_APPS, ROOT_URLCONF y WSGI_APPLICATION no se redeclaran: ya
# llegan heredados del `import *` de arriba, idénticos a settings.py. Antes
# esta lista volvía a escribirse entera aquí, así que cada app nueva había
# que agregarla dos veces -- exactamente lo que paso con 'analitica', que
# quedó sin registrar en esta lista hasta que un test lo hizo evidente.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'db.sqlite3'),
    }
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

REST_FRAMEWORK = {
    # Tupla vacia a proposito (sin auth/permission requeridos en tests);
    # mypy infiere el literal `()` como tuple[()] y no como tuple[str, ...],
    # que es lo que espera el stub de DRF para este valor -- no hay nada
    # que corregir en el tipo, es una limitacion de inferencia con tuplas
    # vacias.
    'DEFAULT_AUTHENTICATION_CLASSES': (),  # type: ignore[dict-item]
    'DEFAULT_PERMISSION_CLASSES': (),  # type: ignore[dict-item]
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
