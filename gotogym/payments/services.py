"""Reembolso real de un pedido ya pagado.

Sustituye el `internal_note` manual ("Requiere reembolso manual") por un
`Refund` que efectivamente llama al proveedor de pago -- el mismo que
proceso el cobro original, no necesariamente el proveedor activo hoy.
"""
from decimal import Decimal

from django.db import transaction as db_transaction

from .models import PaymentTransaction, Refund
from .providers.mercadopago import MercadoPagoPaymentProvider
from .providers.mock import MockPaymentProvider

_PROVIDERS_BY_NAME = {
    'mock': MockPaymentProvider,
    'mercadopago': MercadoPagoPaymentProvider,
}


class RefundError(Exception):
    """Error de negocio que impide procesar el reembolso."""


def get_provider_for_transaction(payment_transaction):
    """El proveedor que efectivamente proceso ese pago.

    Deliberadamente no usa `payments.views.get_active_provider()`: una
    transaccion vieja se reembolsa con el proveedor que la cobro, aunque el
    proveedor activo del sitio haya cambiado despues.
    """
    clase = _PROVIDERS_BY_NAME.get(payment_transaction.provider)
    if clase is None:
        raise RefundError(f"Proveedor de pago desconocido: {payment_transaction.provider!r}.")
    return clase()


@db_transaction.atomic
def refund_order_payment(order, requested_by, amount=None):
    """Reembolsa el pago aprobado de un pedido y deja constancia en `Refund`.

    No cambia `order_status`: el pedido ya deberia estar cancelado o
    marcado como devolucion antes de llamar esto (esa transicion ya revierte
    la comision del afiliado por separado, ver `orders.services`).
    """
    transaccion = (
        order.payment_transactions
        .filter(status=PaymentTransaction.Status.APPROVED)
        .order_by('-created_at')
        .first()
    )
    if transaccion is None:
        raise RefundError('Este pedido no tiene un pago aprobado para reembolsar.')

    if transaccion.refunds.filter(status=Refund.Status.APPROVED).exists():
        raise RefundError('Este pago ya fue reembolsado.')

    monto = Decimal(amount) if amount is not None else transaccion.amount
    provider = get_provider_for_transaction(transaccion)

    try:
        resultado = provider.refund_payment(transaccion, amount=amount)
    except Exception as error:
        Refund.objects.create(
            payment_transaction=transaccion, amount=monto, status=Refund.Status.FAILED,
            requested_by=requested_by, error_message=str(error),
        )
        raise RefundError(f'El proveedor de pago rechazo el reembolso: {error}') from error

    estado = Refund.Status.APPROVED if resultado.get('status') == 'approved' else Refund.Status.PENDING
    return Refund.objects.create(
        payment_transaction=transaccion, amount=monto, status=estado,
        provider_refund_id=resultado.get('provider_refund_id', ''), requested_by=requested_by,
    )
