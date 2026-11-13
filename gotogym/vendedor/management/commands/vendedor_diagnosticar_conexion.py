"""Diagnostico seguro de configuracion del enlace Prime -> Quantum Coach.

No imprime secretos, firmas ni contenido de usuarios; no envia solicitudes.
Uso: python manage.py vendedor_diagnosticar_conexion
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand

from vendedor.coach_client import _url_permitida


class Command(BaseCommand):
    help = "Comprueba la configuracion local de conexion con Quantum Coach sin revelar secretos."

    def handle(self, *args, **options):
        url = settings.COACH_API_URL
        key_id = settings.COACH_SERVICE_KEY_ID
        secret = settings.COACH_SERVICE_SECRET
        parsed = urlsplit(url)
        checks = {
            "URL HTTPS o localhost permitida": bool(url and _url_permitida(url)),
            "Ruta del endpoint esperada": parsed.path == "/api/commerce/agent/message/",
            "Identificador de servicio presente": bool(key_id and key_id.strip()),
            "Identificador con formato valido": bool(key_id and __import__("re").fullmatch(r"[A-Za-z0-9_-]{1,40}", key_id)),
            "Secreto de servicio presente": bool(secret),
            "Secreto sin espacios exteriores": bool(secret and secret == secret.strip()),
            "Cliente real habilitado": not settings.VENDEDOR_COACH_SIMULADO,
        }
        for label, ok in checks.items():
            self.stdout.write(f"{'OK' if ok else 'REVISAR'}: {label}")
        self.stdout.write("El resultado no prueba que el secreto coincida con el backend Django.")
        if not all(checks.values()):
            raise SystemExit(1)
