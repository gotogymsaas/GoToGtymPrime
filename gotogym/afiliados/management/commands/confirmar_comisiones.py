"""Confirma las comisiones cuyo periodo de validacion ya termino.

Es idempotente y se puede programar tan seguido como se quiera (por ejemplo
una vez al dia). El panel del afiliado y el del administrador tambien la
ejecutan al abrirse, asi que la confirmacion no depende de que este comando
este programado: solo hace que ocurra a tiempo cuando nadie abre un panel."""
from django.core.management.base import BaseCommand

from afiliados.services import confirmar_comisiones_vencidas


class Command(BaseCommand):
    help = 'Confirma las comisiones de afiliados cuyo periodo de validación terminó.'

    def handle(self, *args, **options):
        confirmadas = confirmar_comisiones_vencidas()
        self.stdout.write(f'Comisiones confirmadas: {confirmadas}')
