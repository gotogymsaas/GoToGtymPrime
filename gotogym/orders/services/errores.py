"""Errores de negocio del checkout y de las transiciones de un pedido."""
from django.utils.translation import gettext


class CheckoutError(Exception):
    """Error de negocio que impide crear el pedido."""


class EmptyCartError(CheckoutError):
    def __init__(self):
        super().__init__(gettext('Tu carrito está vacío.'))


class OutOfStockError(CheckoutError):
    def __init__(self, faltantes):
        self.faltantes = faltantes
        detalle = '; '.join(
            gettext('%(sku)s: pediste %(pedido)s, quedan %(disponible)s') % {
                'sku': sku, 'pedido': pedido, 'disponible': disponible,
            }
            for sku, pedido, disponible in faltantes
        )
        super().__init__(gettext('No hay unidades suficientes. %(detalle)s') % {'detalle': detalle})


class PaymentNotApprovedError(CheckoutError):
    def __init__(self):
        super().__init__(gettext('El pago todavía no está aprobado.'))


class InvalidOrderTransitionError(CheckoutError):
    def __init__(self, order, nuevo_estado):
        super().__init__(
            f'No se puede pasar de "{order.get_order_status_display()}" a "{nuevo_estado}".'
        )
