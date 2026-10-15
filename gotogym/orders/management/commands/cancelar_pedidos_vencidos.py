"""Cancela los pedidos pendientes de pago cuyo plazo ya vencio.

Es idempotente y se puede programar tan seguido como se quiera (por ejemplo
cada hora). El checkout y el panel tambien la ejecutan, asi que la
cancelacion no depende de que este comando este programado: solo hace que
ocurra a tiempo cuando nadie compra ni abre el panel."""
from django.core.management.base import BaseCommand

from orders.services import cancel_expired_orders


class Command(BaseCommand):
    help = 'Cancela los pedidos pendientes de pago que superaron el plazo y devuelve sus cupones.'

    def handle(self, *args, **options):
        canceladas = cancel_expired_orders()
        self.stdout.write(f'Pedidos cancelados: {canceladas}')
