"""`migrate` que, antes de migrar, adapta una base que venga del programa
cuando se llamaba "influencer" (ver `afiliados.adaptar_base`).

Reemplaza al `migrate` de Django para que el paso nunca dependa de que
alguien se acuerde de ejecutarlo: lo usan por igual el arranque en Azure, el
CI, la base local y la de pruebas (en una base nueva no hace nada).
"""
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
        return super().handle(*args, **options)
