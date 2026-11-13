"""Configuracion de produccion para `manage.py check --deploy` en CI.

No se usa para servir nada: existe para que la verificacion de despliegue
pueda fallar ante cualquier aviso nuevo sin que fallen los dos que el sitio
decidio no atender.
"""
from .settings import *  # noqa: F403

SILENCED_SYSTEM_CHECKS = [
    # HSTS sobre subdominios y en la lista de precarga de los navegadores no
    # se puede deshacer con facilidad: se activan solo con la decision expresa
    # de quien administra el dominio (SECURE_HSTS_INCLUDE_SUBDOMAINS y
    # SECURE_HSTS_PRELOAD).
    'security.W005',
    'security.W021',
]
