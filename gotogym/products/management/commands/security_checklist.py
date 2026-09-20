"""Checklist de solo lectura de variables de entorno sensibles.

No modifica nada. Compara los valores efectivos de `settings` contra lo que
se espera en un entorno de produccion real (DEBUG apagado, SECRET_KEY fuerte,
cookies seguras, panel de simulacion de pagos apagado). El resultado depende
por completo del proceso donde se ejecute: correrlo en local con
`settings_local` siempre marcara advertencias, porque ese entorno esta
pensado para desarrollo, no para produccion.

Sale con codigo 1 si encuentra algo inseguro, para poder usarse como
verificacion automatizada antes de un despliegue.
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Audita settings sensibles del entorno actual (solo lectura, no modifica nada).'

    def handle(self, *args, **options):
        problemas = []
        avisos = []

        self.stdout.write(self.style.MIGRATE_HEADING('Checklist de seguridad (entorno actual)'))

        if settings.DEBUG:
            avisos.append('DEBUG=True (correcto solo en desarrollo local; nunca en produccion real).')

        if settings.SECRET_KEY == 'change-me':
            problemas.append("SECRET_KEY sigue en el valor por defecto 'change-me'.")

        if '*' in settings.ALLOWED_HOSTS:
            avisos.append("ALLOWED_HOSTS incluye '*' (correcto solo en desarrollo local).")
        elif not settings.ALLOWED_HOSTS:
            problemas.append('ALLOWED_HOSTS esta vacio.')

        for nombre in ['SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE']:
            valor = getattr(settings, nombre, False)
            if not valor:
                (avisos if settings.DEBUG else problemas).append(f'{nombre} esta en False.')

        if getattr(settings, 'PAYMENTS_MOCK_UI_ENABLED', False) and not settings.DEBUG:
            problemas.append(
                'PAYMENTS_MOCK_UI_ENABLED=True con DEBUG=False: el panel de simulacion de '
                'pagos quedaria visible en un entorno que no es de desarrollo.'
            )

        db_engine = settings.DATABASES['default']['ENGINE']
        self.stdout.write(f'  Motor de base de datos: {db_engine}')
        if 'sqlite3' in db_engine and not settings.DEBUG:
            avisos.append('El motor de base de datos es SQLite fuera de DEBUG; confirmar que es intencional.')

        self.stdout.write('')
        for etiqueta, lista, estilo in [
            ('Problemas (bloquean produccion)', problemas, self.style.ERROR),
            ('Avisos (revisar segun el entorno)', avisos, self.style.WARNING),
        ]:
            self.stdout.write(self.style.MIGRATE_HEADING(f'{etiqueta}: {len(lista)}'))
            for item in lista:
                self.stdout.write(estilo(f'  - {item}'))

        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'RECORDATORIO: este comando solo audita el proceso donde corre. No confirma nada '
            'sobre el entorno real de Azure; para eso hay que ejecutarlo alli directamente o '
            'con las mismas variables de entorno cargadas.'
        ))

        if problemas:
            raise SystemExit(1)
