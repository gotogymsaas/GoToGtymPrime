"""Cancelacion de los pedidos que nadie pago a tiempo."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from gotogym.tasks import enqueue

from .. import correos
from ..models import Order, OrderStatus, PaymentStatus
from .estados import _anotar, _liberar_lo_reservado, _registrar_estado


def cancel_expired_orders(ahora=None, horas=None):
    """Cancela los pedidos que siguen pendientes de pago pasado el plazo.

    Un pedido pendiente no reserva stock, pero si consume un uso de su cupon
    y queda abierto para siempre. Pasado el plazo (`ORDER_PAYMENT_WINDOW_HOURS`,
    48 horas por defecto) se cancela, se devuelve el cupon y se avisa a la
    persona. No se toca un pedido cuyo pago sigue en verificacion en el
    proveedor (una transaccion pendiente con `payment_id`): puede aprobarse
    todavia, por ejemplo un pago en efectivo.

    Devuelve cuantos pedidos canceló. Es idempotente y se puede programar tan
    seguido como se quiera; el checkout y el panel tambien la ejecutan, así
    que no depende de que haya una tarea periodica."""
    ahora = ahora or timezone.now()
    horas = horas if horas is not None else settings.ORDER_PAYMENT_WINDOW_HOURS
    limite = ahora - timedelta(hours=horas)

    candidatos = Order.objects.filter(
        order_status=OrderStatus.PENDING_PAYMENT, created_at__lt=limite,
    ).values_list('pk', flat=True)

    canceladas = 0
    for pk in list(candidatos):
        with transaction.atomic():
            pedido = Order.objects.select_for_update().get(pk=pk)
            if pedido.order_status != OrderStatus.PENDING_PAYMENT:
                continue
            if pedido.payment_transactions.filter(
                status=PaymentStatus.PENDING,
            ).exclude(payment_id='').exists():
                continue
            pedido.order_status = OrderStatus.CANCELLED
            pedido.payment_status = PaymentStatus.CANCELLED
            pedido.cancelled_at = ahora
            pedido.internal_note = _anotar(
                pedido.internal_note, f'Cancelado automáticamente: sin pago tras {horas} horas.',
            )
            pedido.save(update_fields=['order_status', 'payment_status', 'cancelled_at', 'internal_note', 'updated_at'])
            _registrar_estado(
                pedido, OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED,
                nota=f'Sin pago tras {horas} horas.',
            )
            _liberar_lo_reservado(pedido, f'Pedido {pedido.order_number} sin pago a tiempo.')
            enqueue(correos.pedido_cancelado, pedido.pk)
            canceladas += 1
    return canceladas
