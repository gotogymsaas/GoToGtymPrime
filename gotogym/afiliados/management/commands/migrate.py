"""`migrate` que, antes de migrar, adapta una base que venga del programa
cuando se llamaba "influencer" (ver `afiliados.adaptar_base`) y, despues,
crea la tabla de la cache si esta vive en la base de datos.

Reemplaza al `migrate` de Django para que el paso nunca dependa de que
alguien se acuerde de ejecutarlo: lo usan por igual el arranque en Azure, el
CI, la base local y la de pruebas (en una base nueva no hace nada).
"""
from django.conf import settings
from django.core.management import call_command
from django.core.management.commands.migrate import Command as MigrateCommand
from django.db import connections

from afiliados.adaptar_base import adaptar_base


class Command(MigrateCommand):
    def handle(self, *args, **options):
        # `--plan` y `--check` solo consultan: no deben modificar la base.
        if not options.get('plan') and not options.get('check_unapplied'):
            connection = connections[options.get('database') or 'default']
            if adaptar_base(connection, escribir=self.stdout.write):
                self.stdout.write(self.style.SUCCESS('Base adaptada al nombre "afiliados".'))
        resultado = super().handle(*args, **options)
        # Si la cache compartida vive en la base de datos, su tabla se crea
        # aqui: asi existe en cualquier lugar donde se migre, sin otro paso.
        if not options.get('plan') and not options.get('check_unapplied') and any(
            cache['BACKEND'].endswith('DatabaseCache') for cache in settings.CACHES.values()
        ):
            call_command('createcachetable', verbosity=0)
        return resultado
