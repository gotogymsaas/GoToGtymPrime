"""Muestra la factura que se enviaria a Alegra para un pedido, sin enviarla.

No hace ninguna llamada de red ni escribe en la base de datos, y funciona con
la facturacion apagada: sirve para revisar importes, impuestos y datos del
cliente antes de activar la integracion. Los ids de Alegra (cliente y
productos) aparecen como marcadores, porque solo se conocen al emitir."""
import json

from django.core.management.base import BaseCommand, CommandError

from orders import facturacion
from orders.models import Order


class Command(BaseCommand):
    help = 'Imprime el cliente y la factura que se enviarían a Alegra para un pedido (no envía nada).'

    def add_arguments(self, parser):
        parser.add_argument('order_number', help='Número del pedido, por ejemplo GTG-202610-0001.')

    def handle(self, *args, **options):
        order = (
            Order.objects.select_related('address', 'user')
            .filter(order_number=options['order_number']).first()
        )
        if order is None:
            raise CommandError(f"No existe el pedido {options['order_number']}.")

        self.stdout.write(f'Pedido {order.order_number} ({order.get_payment_status_display()}, '
                          f'{order.get_order_status_display()})')
        if not facturacion.facturable(order):
            self.stdout.write('Aviso: este pedido no se facturaría (no está pagado o está cancelado).')

        try:
            contacto = facturacion.armar_contacto(order)
        except (facturacion.FacturacionError, KeyError) as error:
            contacto = None
            self.stdout.write(f'Cliente: no se puede armar ({error or "tipo de documento desconocido"}).')
        if contacto:
            self.stdout.write('\nCliente (POST /contacts, solo si no existe en Alegra):')
            self.stdout.write(json.dumps(contacto, ensure_ascii=False, indent=2))

        marcadores = {linea.sku_snapshot: '<id-producto-alegra>' for linea in order.items.all()}
        marcadores[facturacion.REFERENCIA_ENVIO] = '<id-envio-alegra>'
        cuerpo = facturacion.armar_factura(
            order, '<id-cliente-alegra>', marcadores, pago=facturacion.pago_aprobado(order),
        )
        self.stdout.write('\nFactura (POST /invoices):')
        self.stdout.write(json.dumps(cuerpo, ensure_ascii=False, indent=2))
