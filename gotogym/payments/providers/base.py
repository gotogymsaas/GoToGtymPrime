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
