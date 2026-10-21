"""Proveedor de pago real (Mercado Pago, Checkout Pro).

Implementa la misma interfaz que el proveedor simulado, para que activar un
proveedor real sea cuestion de configuracion (`PAYMENT_PROVIDER=mercadopago`)
y no de rediseñar el checkout. Por defecto, en todo entorno que no declare
esa variable explicitamente, el checkout sigue usando el proveedor mock.

Flujo: se crea una preferencia, el comprador paga en el sitio de Mercado Pago
(`init_point`) y vuelve a la tienda. El estado real nunca se toma de lo que
llega por la URL o el webhook: se consulta el pago a la API de Mercado Pago.
"""
import logging
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.urls import reverse
from integrations.mercadopago.mercadopago_client import MercadoPagoClient

from ..models import PaymentTransaction
from .base import PaymentProvider

logger = logging.getLogger(__name__)

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
                'title': 'Envío',
                'quantity': 1,
                'unit_price': float(order.shipping_cost),
                'currency_id': order.currency,
            })

        if order.discount_total:
            # Mercado Pago no admite items con precio negativo, asi que un
            # descuento no se puede mostrar como una linea mas. Sin esto el
            # comprador pagaba el total sin descuento. Se cobra un solo item
            # con el total real del pedido.
            items = [{
                'title': f'Pedido GoToGym {order.order_number}',
                'quantity': 1,
                'unit_price': float(order.total),
                'currency_id': order.currency,
            }]

        base = settings.SITIO_URL
        retorno = base + reverse('payments:return', args=[order.order_number])
        preferencia = {
            'items': items,
            'external_reference': order.order_number,
            'back_urls': {'success': retorno, 'failure': retorno, 'pending': retorno},
            'statement_descriptor': 'GOTOGYM',
        }
        # Mercado Pago solo acepta `auto_return` con back_urls https, y solo
        # puede avisar a una `notification_url` publica. En local (http) el
        # comprador vuelve con el boton "Volver al sitio" y la vista de
        # retorno consulta el pago igualmente.
        if base.startswith('https://'):
            preferencia['auto_return'] = 'approved'
            preferencia['notification_url'] = base + reverse('mercadopago_webhook')
        return preferencia

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

    def refund_payment(self, payment_transaction, amount=None):
        """Reembolsa el pago real en Mercado Pago.

        Requiere `payment_id` (el pago ya debe estar aprobado): no tiene
        sentido reembolsar una preferencia que nunca se pago."""
        if not payment_transaction.payment_id:
            raise ValueError('No hay payment_id: este pago nunca fue aprobado por Mercado Pago.')
        respuesta = self.client.refund_payment(
            payment_transaction.payment_id,
            amount=float(amount) if amount is not None else None,
        )
        return {
            'provider_refund_id': str(respuesta.get('id', '')),
            'status': respuesta.get('status', ''),
        }

    def checkout_url(self, payment_transaction):
        """URL del sitio de Mercado Pago donde el comprador paga, o '' si la
        transaccion no viene de una preferencia real."""
        return (payment_transaction.raw_payload or {}).get('init_point', '')

    def sync_payment(self, payment_id):
        """Consulta el pago a Mercado Pago y aplica su estado a la
        transaccion que le corresponde. Devuelve la transaccion.

        Es el unico camino por el que cambia un estado: lo que traen el
        webhook o la URL de retorno solo dicen "revisa este pago", porque
        cualquiera puede escribir esos parametros. El pedido se identifica por
        `external_reference` y se exige que importe y moneda coincidan con lo
        que se le cobro al comprador.

        Idempotente: si ya se aplico (mismo payment_id y mismo estado), no
        vuelve a escribir nada. Lanza `PaymentTransaction.DoesNotExist` si no
        encuentra a que transaccion corresponde.
        """
        payment_id = str(payment_id)
        pago = self.client.get_payment(payment_id)
        external_reference = pago.get('external_reference') or ''

        transaction = PaymentTransaction.objects.filter(provider=self.name, payment_id=payment_id).first()
        if transaction is None and external_reference:
            transaction = (
                PaymentTransaction.objects
                .filter(provider=self.name, external_reference=external_reference)
                .order_by('-created_at')
                .first()
            )
        if transaction is None:
            raise PaymentTransaction.DoesNotExist(
                f'No se encontró una transacción para el pago '
                f'(payment_id={payment_id!r}, external_reference={external_reference!r}).'
            )

        if not self._coincide_con_lo_cobrado(pago, transaction):
            logger.error(
                'El pago %s de Mercado Pago no coincide con lo cobrado en %s '
                '(pago: %s %s; esperado: %s %s). No se aplica.',
                payment_id, transaction.external_reference,
                pago.get('transaction_amount'), pago.get('currency_id'),
                transaction.amount, transaction.currency,
            )
            return transaction

        nuevo_estado = _MAPA_ESTADOS_MP.get(pago.get('status', ''))
        ya_procesada = (
            nuevo_estado is None
            or (transaction.status == nuevo_estado and transaction.payment_id == payment_id)
        )
        if ya_procesada:
            return transaction

        transaction.payment_id = payment_id
        transaction.status = nuevo_estado
        # La preferencia (con su `init_point`) se conserva: el comprador puede
        # volver a pagar con ella tras un rechazo.
        transaction.raw_payload = {**(transaction.raw_payload or {}), 'payment': pago}
        transaction.save(update_fields=['payment_id', 'status', 'raw_payload', 'updated_at'])
        return transaction

    @staticmethod
    def _coincide_con_lo_cobrado(pago, transaction):
        try:
            importe = Decimal(str(pago.get('transaction_amount')))
        except (InvalidOperation, TypeError):
            return False
        return importe == transaction.amount and pago.get('currency_id') == transaction.currency

    def handle_callback(self, payload):
        """Procesa la notificacion de un webhook y devuelve la transaccion
        actualizada (ver `sync_payment`).

        Una notificacion real de Mercado Pago solo trae el id del pago
        (`{"type": "payment", "data": {"id": "123"}}`); el estado se consulta.
        """
        datos = payload.get('data') or {}
        payment_id = str(datos.get('id') or payload.get('id') or '')
        if not payment_id:
            raise PaymentTransaction.DoesNotExist('La notificación no trae el id del pago.')
        return self.sync_payment(payment_id)
