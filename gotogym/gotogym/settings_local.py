"""
Configuración local para desarrollo
Usa SQLite en lugar de MySQL Azure para desarrollo seguro
"""
import os
from pathlib import Path


def _cargar_env(ruta):
    """Carga `KEY=valor` de un `.env` local (ignorado por git) sin pisar
    variables que ya esten definidas en el entorno. Una variable definida pero
    VACIA se trata como ausente: la terminal de VS Code (`python.terminal.useEnvFile`)
    guarda una copia del `.env` al abrirse, y si el token se pego despues, esa
    copia vieja lo dejaba vacio e impedia leer el valor actual. Debe correr
    antes de importar `settings`, que lee `os.environ` al importarse."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        clave, _, valor = linea.partition('=')
        clave = clave.strip()
        if not os.environ.get(clave):
            os.environ[clave] = valor.strip().strip('"\'')


_cargar_env(Path(__file__).resolve().parent.parent.parent / '.env')

from .settings import *  # noqa: E402,F403

# Base de datos SQLite local para desarrollo
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'db_local.sqlite3'),
    }
}

# Debug siempre activo en local
DEBUG = True

# Con DEBUG Django muestra su pagina tecnica amarilla en vez de las paginas de
# error del sitio. Aqui se reemplaza por las nuestras (ver
# gotogym.errores.PaginaDeErrorMiddleware); el traceback sigue saliendo en la
# consola y en logs/errores.txt. Para ver la pagina de Django, arrancar con
# PAGINA_TECNICA_DJANGO=1.
REEMPLAZAR_PAGINAS_DE_DEBUG = os.environ.get('PAGINA_TECNICA_DJANGO') != '1'

# Permitir todos los hosts en desarrollo
ALLOWED_HOSTS = ['*']

# Configuración simple de email para desarrollo
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Configuración de idioma para desarrollo
LANGUAGE_CODE = 'es'

print("✅ Usando configuración LOCAL (SQLite)")
print(f"Base de datos: {DATABASES['default']['NAME']}")
