from .settings import *

# INSTALLED_APPS, ROOT_URLCONF y WSGI_APPLICATION no se redeclaran: ya
# llegan heredados del `import *` de arriba, idénticos a settings.py. Antes
# esta lista volvía a escribirse entera aquí, así que cada app nueva había
# que agregarla dos veces -- exactamente lo que paso con 'analitica', que
# quedó sin registrar en esta lista hasta que un test lo hizo evidente.

# En memoria, no en `db.sqlite3`: la suite crea su propia base de pruebas, y
# comandos como `makemigrations --check` (que valida el historial de la base
# a la que apuntan) no deben depender de un archivo local con el estado en que
# lo dejo la ultima vez que alguien migro. Con un archivo viejo, el hook de
# pre-push fallaba con InconsistentMigrationHistory mientras el CI -- que parte
# de una base vacia -- pasaba. Asi se comportan igual.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# El material de marca de las pruebas no debe mezclarse con el real.
import tempfile  # noqa: E402

RECURSOS_AFILIADOS_ROOT = str(Path(tempfile.gettempdir()) / 'gotogym_pruebas_recursos_afiliados')

RATE_LIMIT_ENABLED = False

# La migracion administracion.0006 carga el catalogo ampliado en las bases reales. La base de
# pruebas parte del catalogo base y cada prueba arma lo que necesita: con esta bandera apagada
# la migracion no hace nada y no altera productos, orden, visibilidad ni inventario.
CATALOGO_AMPLIACION_EN_MIGRACION = False

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
