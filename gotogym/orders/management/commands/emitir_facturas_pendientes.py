"""Emite en Alegra las facturas pendientes y reintenta las fallidas.

Es idempotente y se puede programar seguido (por ejemplo cada 15 minutos): una
factura ya emitida no se vuelve a emitir. Existe porque la emision al confirmar
el pago puede fallar si Alegra no responde, y ese pago no se reintenta solo.
Con `ALEGRA_FACTURAR_DESDE` tambien factura los pedidos pagados desde esa fecha
que nunca tuvieron factura."""
from django.core.management.base import BaseCommand

from orders.facturacion import emitir_factura, facturacion_activa, ordenes_por_facturar
from orders.models import InvoiceStatus


class Command(BaseCommand):
    help = 'Emite las facturas de Alegra pendientes y reintenta las que fallaron.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite', type=int, default=50,
            help='Máximo de pedidos a procesar en esta ejecución (50 por defecto).',
        )

    def handle(self, *args, **options):
        if not facturacion_activa():
            self.stdout.write('Facturación desactivada: no se hizo nada.')
            return

        emitidas = fallidas = 0
        for order_id in ordenes_por_facturar(options['limite']):
            estado = emitir_factura(order_id)
            if estado == InvoiceStatus.ISSUED:
                emitidas += 1
            elif estado == InvoiceStatus.FAILED:
                fallidas += 1
        self.stdout.write(f'Facturas emitidas: {emitidas}. Fallidas: {fallidas}.')
