"""Resuelve los reembolsos que quedaron pendientes consultando al proveedor.

Un reembolso queda pendiente cuando el proveedor no dio una respuesta
definitiva (tiempo agotado, caida del proceso a mitad de la solicitud). Hasta
resolverlo bloquea nuevos intentos para no devolver el dinero dos veces.

    python manage.py conciliar_reembolsos            # los resuelve
    python manage.py conciliar_reembolsos --simular  # solo muestra que haria
"""
from django.core.management.base import BaseCommand

from payments.models import Refund
from payments.services import RefundError, conciliar_reembolso


class Command(BaseCommand):
    help = 'Concilia con el proveedor los reembolsos que siguen pendientes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simular', action='store_true',
            help='Lista los reembolsos pendientes sin consultar ni modificar nada.',
        )

    def handle(self, *args, **opciones):
        pendientes = Refund.objects.filter(status=Refund.Status.PENDING).select_related(
            'payment_transaction__order',
        )
        if not pendientes:
            self.stdout.write('No hay reembolsos pendientes.')
            return
        for reembolso in pendientes:
            pedido = reembolso.payment_transaction.order.order_number
            if opciones['simular']:
                self.stdout.write(f'Pendiente: {pedido} ${reembolso.amount} (creado {reembolso.created_at:%Y-%m-%d %H:%M})')
                continue
            try:
                conciliar_reembolso(reembolso)
            except RefundError as error:
                self.stdout.write(self.style.WARNING(f'{pedido}: sin resolver. {error}'))
            else:
                self.stdout.write(f'{pedido}: {reembolso.get_status_display()}.')
