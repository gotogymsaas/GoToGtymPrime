"""Proveedor de pago simulado.

No cobra nada de verdad: crea el intento de pago y expone `force_status`
para que una pantalla de pruebas pueda mover el estado a mano. Sirve para
ejercitar el flujo completo de checkout sin credenciales de ningun
proveedor real.
"""
import uuid

from ..models import PaymentTransaction
from .base import PaymentProvider


class MockPaymentProvider(PaymentProvider):
    name = 'mock'

    # Reintentar sobre un intento que ya quedo en uno de estos estados no
    # tiene sentido: crea uno nuevo en vez de reabrir un pago cerrado.
    _ESTADOS_CERRADOS = {PaymentTransaction.Status.REJECTED, PaymentTransaction.Status.CANCELLED}

    def create_payment_intent(self, order):
        vigente = (
            PaymentTransaction.objects
            .filter(order=order, provider=self.name)
            .exclude(status__in=self._ESTADOS_CERRADOS)
            .order_by('-created_at')
            .first()
        )
        if vigente:
            return vigente

        return PaymentTransaction.objects.create(
            order=order,
            provider=self.name,
            preference_id=f"mock-pref-{uuid.uuid4().hex[:12]}",
            external_reference=order.order_number,
            status=PaymentTransaction.Status.PENDING,
            amount=order.total,
            currency=order.currency,
            idempotency_key=str(uuid.uuid4()),
        )

    def get_status(self, payment_transaction):
        return payment_transaction.status

    def handle_callback(self, payload):
        raise NotImplementedError(
            'El proveedor mock no recibe webhooks reales; usa force_status.'
        )

    def force_status(self, payment_transaction, status):
        """Fuerza un estado sin pasar por ningun webhook real.

        Repetir el mismo estado no crea ni modifica nada: es lo que evita
        que un doble clic (o un doble envio de formulario) duplique el
        efecto de la simulacion.
        """
        if payment_transaction.status == status:
            return payment_transaction

        payment_transaction.status = status
        if status == PaymentTransaction.Status.APPROVED and not payment_transaction.payment_id:
            payment_transaction.payment_id = f"mock-pay-{uuid.uuid4().hex[:12]}"
        payment_transaction.save(update_fields=['status', 'payment_id', 'updated_at'])
        return payment_transaction
