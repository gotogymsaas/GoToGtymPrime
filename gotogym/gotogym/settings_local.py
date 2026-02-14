"""
Configuración local para desarrollo
Usa SQLite en lugar de MySQL Azure para desarrollo seguro
"""
from .settings import *

# Base de datos SQLite local para desarrollo
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_local.sqlite3',
    }
}

# Debug siempre activo en local
DEBUG = True

# Permitir todos los hosts en desarrollo
ALLOWED_HOSTS = ['*']

# Configuración simple de email para desarrollo
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Configuración de idioma para desarrollo
LANGUAGE_CODE = 'es'

print("✅ Usando configuración LOCAL (SQLite)")
print(f"📁 Base de datos: {DATABASES['default']['NAME']}")
