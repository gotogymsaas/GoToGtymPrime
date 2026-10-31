"""Levanta un Coach simulado local para probar el asistente de compras.

    python manage.py vendedor_simular_coach
    COACH_API_URL=http://127.0.0.1:8002/api/commerce/agent/message/

Usa la clave y el secreto de COACH_SERVICE_KEY_ID y COACH_SERVICE_SECRET, o los
que se pasen por opcion. Ver `vendedor/simulador.py`.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from vendedor import simulador


class Command(BaseCommand):
    help = 'Levanta un Coach simulado que verifica la firma de la tienda y responde segun el contrato.'

    def add_arguments(self, parser):
        parser.add_argument('--host', default='127.0.0.1')
        # 8001 se deja libre para el Coach real cuando se pruebe contra el.
        parser.add_argument('--port', type=int, default=8002)
        parser.add_argument('--modo', choices=simulador.MODOS, default='ok')
        parser.add_argument('--demora', type=float, default=20.0, help='Segundos de espera en el modo lento.')
        parser.add_argument('--clave-id', default=settings.COACH_SERVICE_KEY_ID)
        parser.add_argument('--secreto', default=settings.COACH_SERVICE_SECRET)

    def handle(self, *args, **opciones):
        if not opciones['clave_id'] or not opciones['secreto']:
            raise CommandError(
                'Faltan COACH_SERVICE_KEY_ID y COACH_SERVICE_SECRET (o --clave-id y --secreto): '
                'sin ellos no se puede verificar la firma.'
            )
        servidor = simulador.crear_servidor(
            opciones['host'], opciones['port'], opciones['clave_id'], opciones['secreto'],
            modo=opciones['modo'], demora=opciones['demora'],
            registro=lambda linea: self.stdout.write(linea),
        )
        url = f"http://{opciones['host']}:{opciones['port']}{simulador.RUTA}"
        self.stdout.write(self.style.SUCCESS(f"Coach simulado ({opciones['modo']}) en {url}"))
        self.stdout.write('Ctrl+C para detenerlo.')
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            self.stdout.write('Detenido.')
        finally:
            servidor.server_close()
