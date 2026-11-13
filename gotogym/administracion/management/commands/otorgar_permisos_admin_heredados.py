"""Revisa las cuentas de staff sin grupo y, solo a las que se indiquen, les da
el paquete completo de permisos del panel.

Sin argumentos solo lista, no modifica nada:

    python manage.py otorgar_permisos_admin_heredados
    python manage.py otorgar_permisos_admin_heredados --otorgar ana@gotogym.store

Una cuenta de staff sin grupo y sin el paquete completo es una cuenta heredada
de antes de los permisos granulares: el panel hoy le completa el paquete la
primera vez que entra, lo que tambien afecta a quien se quiso dejar con menos.
Este comando permite decidir cuenta por cuenta y es el paso previo a retirar
ese autoajuste.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from administracion.permissions import ADMIN_PERM_CODENAMES, grant_full_admin_permissions


class Command(BaseCommand):
    help = 'Lista las cuentas de staff sin grupo y otorga el paquete completo a las indicadas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--otorgar', nargs='+', metavar='CORREO',
            help='Correos de las cuentas a las que se les da el paquete completo.',
        )

    def handle(self, *args, **opciones):
        User = get_user_model()
        candidatas = [
            usuario
            for usuario in User.objects.filter(is_staff=True, is_superuser=False)
            .order_by('email').prefetch_related('groups')
            if not usuario.groups.exists() and not usuario.has_perms(ADMIN_PERM_CODENAMES)
        ]

        if not opciones['otorgar']:
            if not candidatas:
                self.stdout.write('No hay cuentas de staff sin grupo que revisar.')
                return
            self.stdout.write('Cuentas de staff sin grupo ni paquete completo:')
            for usuario in candidatas:
                self.stdout.write(f'  {usuario.email}')
            return

        por_correo = {usuario.email.lower(): usuario for usuario in candidatas}
        desconocidas = [c for c in opciones['otorgar'] if c.lower() not in por_correo]
        if desconocidas:
            raise CommandError(
                'No son cuentas de staff sin grupo pendientes de revisar: ' + ', '.join(desconocidas),
            )
        for correo in opciones['otorgar']:
            grant_full_admin_permissions(por_correo[correo.lower()])
            self.stdout.write(f'Paquete completo otorgado a {correo}.')
