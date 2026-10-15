"""Busca cuentas que todavia aceptan una contrasena que estuvo publicada.

Una migracion antigua creaba el administrador `admin@gotogym.com`
(usuario `ericviana`) con una contrasena escrita en el codigo, y ese codigo
esta en el historial de git. Si una base se migro entonces, la cuenta sigue
aceptandola. Este comando lo comprueba en cualquier base (sin guardar ni
mostrar contrasenas de nadie) y, con `--rotar`, cambia la contrasena de las
cuentas afectadas por una aleatoria que se muestra una sola vez.

Uso en el entorno que se quiere revisar:

    python manage.py revisar_claves_heredadas            # solo informa
    python manage.py revisar_claves_heredadas --rotar    # informa y corrige
"""
import secrets
import string

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

# Contrasenas que estuvieron escritas en el codigo versionado.
CLAVES_PUBLICADAS = ('EricViana@2026',)


def clave_aleatoria():
    """Cumple las reglas de contrasena de la tienda (mayuscula, minuscula,
    numero y caracter especial)."""
    alfabeto = string.ascii_letters + string.digits + '!?#$@%'
    while True:
        clave = ''.join(secrets.choice(alfabeto) for _ in range(20))
        if (any(c.islower() for c in clave) and any(c.isupper() for c in clave)
                and any(c.isdigit() for c in clave) and any(c in '!?#$@%' for c in clave)):
            return clave


class Command(BaseCommand):
    help = 'Detecta (y con --rotar corrige) cuentas que aceptan una contrasena que estuvo publicada en el codigo.'

    def add_arguments(self, parser):
        parser.add_argument('--rotar', action='store_true', help='Cambia la contrasena de las cuentas afectadas.')

    def handle(self, *args, **options):
        afectadas = [
            usuario for usuario in get_user_model().objects.filter(is_active=True)
            if any(usuario.check_password(clave) for clave in CLAVES_PUBLICADAS)
        ]
        if not afectadas:
            self.stdout.write(self.style.SUCCESS('Ninguna cuenta acepta una contrasena publicada.'))
            return
        for usuario in afectadas:
            rol = 'superusuario' if usuario.is_superuser else 'personal' if usuario.is_staff else 'cliente'
            self.stdout.write(self.style.ERROR(f'AFECTADA: {usuario.email} ({rol})'))
            if options['rotar']:
                nueva = clave_aleatoria()
                usuario.set_password(nueva)
                usuario.save(update_fields=['password'])
                self.stdout.write(f'  Nueva contrasena (guardala ahora, no se vuelve a mostrar): {nueva}')
        if not options['rotar']:
            self.stdout.write('Vuelve a ejecutar con --rotar para cambiarlas.')
