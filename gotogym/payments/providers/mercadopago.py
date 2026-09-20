"""Proveedor de pago real (Mercado Pago), preparado pero no activado.

Implementa la misma interfaz que el proveedor simulado, para que activar un
proveedor real sea cuestion de configuracion (`PAYMENT_PROVIDER=mercadopago`)
y no de rediseñar el checkout. Por defecto, en todo entorno que no declare
esa variable explicitamente, el checkout sigue usando el proveedor mock.
"""
import uuid

from integrations.mercadopago.mercadopago_client import MercadoPagoClient

from ..models import PaymentTransaction
from .base import PaymentProvider

# Estados que Mercado Pago reporta en sus pagos, mapeados a los cuatro
# estados internos. Cualquier valor no reconocido se ignora (no se cambia el
# estado actual de la transaccion) en vez de asumir un mapeo por defecto.
_MAPA_ESTADOS_MP = {
    'approved': PaymentTransaction.Status.APPROVED,
    'pending': PaymentTransaction.Status.PENDING,
    'in_process': PaymentTransaction.Status.PENDING,
    'authorized': PaymentTransaction.Status.PENDING,
    'rejected': PaymentTransaction.Status.REJECTED,
    'cancelled': PaymentTransaction.Status.CANCELLED,
    'refunded': PaymentTransaction.Status.CANCELLED,
    'charged_back': PaymentTransaction.Status.CANCELLED,
}

# Un intento en uno de estos estados ya esta cerrado: un nuevo intento de
# pago sobre la misma orden crea una transaccion nueva en vez de reabrir esta.
_ESTADOS_CERRADOS = {PaymentTransaction.Status.REJECTED, PaymentTransaction.Status.CANCELLED}


class MercadoPagoPaymentProvider(PaymentProvider):
    name = 'mercadopago'

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        # Se crea perezosamente: instanciar MercadoPagoClient exige el
        # paquete `mercadopago` y un access token validos, y este proveedor
        # no debe fallar solo por importarse en un entorno donde no esta
        # activo (PAYMENT_PROVIDER=mock, el default).
        if self._client is None:
            self._client = MercadoPagoClient()
        return self._client

    def _build_preference_data(self, order):
        """Arma los items de la preferencia incluyendo el envio como un
        item mas: es la correccion explicita del bug original, donde el
        envio se mostraba en el carrito y en la Order pero nunca llegaba a
        la preferencia de Mercado Pago.
        """
        items = [
            {
                'title': f"{item.product_name_snapshot} ({item.size_snapshot}/{item.color_snapshot})",
                'quantity': item.quantity,
                'unit_price': float(item.unit_price_snapshot),
                'currency_id': order.currency,
            }
            for item in order.items.all()
        ]

        if order.shipping_cost:
            items.append({
                'title': 'Envio',
                'quantity': 1,
                'unit_price': float(order.shipping_cost),
                'currency_id': order.currency,
            })

        return {
            'items': items,
            'external_reference': order.order_number,
        }

    def create_payment_intent(self, order):
        vigente = (
            PaymentTransaction.objects
            .filter(order=order, provider=self.name)
            .exclude(status__in=_ESTADOS_CERRADOS)
            .order_by('-created_at')
            .first()
        )
        if vigente:
            return vigente

        preferencia = self.client.create_preference(self._build_preference_data(order))

        return PaymentTransaction.objects.create(
            order=order,
            provider=self.name,
            preference_id=preferencia.get('id', ''),
            external_reference=order.order_number,
            status=PaymentTransaction.Status.PENDING,
            amount=order.total,
            currency=order.currency,
            idempotency_key=str(uuid.uuid4()),
            raw_payload=preferencia,
        )

    def get_status(self, payment_transaction):
        return payment_transaction.status

    def handle_callback(self, payload):
        """Procesa una notificacion de webhook y devuelve la transaccion
        actualizada.

        Idempotente: si la notificacion ya se proceso antes (mismo
        payment_id y mismo estado), no vuelve a escribir nada. Lanza
        `PaymentTransaction.DoesNotExist` si no encuentra a que transaccion
        corresponde, para que la vista pueda responder distinto a "ya se
        proceso" que a "no se de que orden habla esto".
        """
        datos = payload.get('data') or {}
        payment_id = str(datos.get('id') or payload.get('id') or '')
        external_reference = payload.get('external_reference')

        transaction = None
        if payment_id:
            transaction = PaymentTransaction.objects.filter(
                provider=self.name, payment_id=payment_id,
            ).first()
        if transaction is None and external_reference:
            transaction = (
                PaymentTransaction.objects
                .filter(provider=self.name, external_reference=external_reference)
                .order_by('-created_at')
                .first()
            )
        if transaction is None:
            raise PaymentTransaction.DoesNotExist(
                f'No se encontro una transaccion para procesar el webhook '
                f'(payment_id={payment_id!r}, external_reference={external_reference!r}).'
            )

        estado_reportado = payload.get('status', '')
        nuevo_estado = _MAPA_ESTADOS_MP.get(estado_reportado)

        ya_procesada = (
            nuevo_estado is None
            or (transaction.status == nuevo_estado and transaction.payment_id == payment_id)
        )
        if ya_procesada:
            return transaction

        transaction.payment_id = payment_id or transaction.payment_id
        transaction.status = nuevo_estado
        transaction.raw_payload = payload
        transaction.save(update_fields=['payment_id', 'status', 'raw_payload', 'updated_at'])
        return transaction
