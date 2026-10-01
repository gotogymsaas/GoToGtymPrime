"""Interfaz de proveedor de pago.

No debe referenciar ningun proveedor concreto: se tiene que poder
implementar una pasarela real con esta misma forma sin tocar `checkout`,
`orders` ni las vistas de `payments`.
"""
from abc import ABC, abstractmethod


class PaymentProvider(ABC):

    @abstractmethod
    def create_payment_intent(self, order):
        """Crea (o recupera) el intento de pago vigente de un pedido.
        Devuelve un `PaymentTransaction`."""

    @abstractmethod
    def get_status(self, payment_transaction):
        """Estado actual del intento de pago segun el proveedor."""

    @abstractmethod
    def handle_callback(self, payload):
        """Procesa una notificacion asincrona del proveedor (webhook) y
        devuelve el `PaymentTransaction` actualizado."""

    @abstractmethod
    def refund_payment(self, payment_transaction, amount=None):
        """Reembolsa un pago ya aprobado, total o parcialmente.

        Devuelve un dict con al menos `provider_refund_id` y `status`. No
        cambia el estado logistico del pedido: eso lo decide quien llama
        (ver `payments.services.refund_order_payment`)."""
