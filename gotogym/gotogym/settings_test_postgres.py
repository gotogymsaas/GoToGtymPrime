"""Pruebas contra PostgreSQL, el motor de produccion.

SQLite no implementa `select_for_update` (lo ignora), asi que los bloqueos
que protegen pagos, inventario y comisiones solo se ejercitan aqui. Los datos
de conexion salen de las variables `POSTGRES_*`; el servicio del CI las
declara y en local se pueden apuntar a cualquier PostgreSQL desechable.
"""
import os

from .settings_test import *  # noqa: F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'gotogym'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}
