"""Efecto de un pago sobre el pedido: confirmarlo (o cancelarlo si ya no se
puede cumplir), confirmar sin cobrar en el modo de pruebas y dejar constancia
de un cobro que el proveedor revirtio."""
import logging

from django.db import transaction
from django.utils import timezone
from gotogym.tasks import enqueue
from inventory.services import InsufficientStockError, decrement_stock

from .. import correos, facturacion, tarjetas_regalo
from ..models import GiftCard, Order, OrderStatus, PaymentStatus
from ..senales import pedido_anulado, pedido_cobrado
from .errores import PaymentNotApprovedError
from .estados import _anotar, _liberar_lo_reservado, _registrar_estado

# Nombre fijo (el del modulo que antes lo contenia todo): es el que los
# filtros de registro y las alertas ya conocen.
logger = logging.getLogger('orders.services')


def registrar_pago_revertido(order, motivo):
    """Deja constancia de un pago aprobado que el proveedor revirtio por su
    cuenta (contracargo, o un reembolso hecho desde su propio panel).

    Anota el pedido, anula la comision del afiliado y registra un error para
    que llegue a quien monitorea (Sentry). No cambia el estado logistico ni el
    de pago del pedido: un contracargo puede disputarse y el paquete puede
    estar ya entregado, asi que decide una persona."""
    order.internal_note = _anotar(
        order.internal_note,
        f'{motivo} Revisar con el proveedor de pago antes de actuar sobre el pedido.',
    )
    order.save(update_fields=['internal_note', 'updated_at'])
    pedido_anulado.send(sender=Order, order=order, motivo=motivo)
    if order.is_gift_card_purchase:
        # El saldo de una tarjeta cuyo pago se revirtio no esta respaldado: se
        # bloquea (sin anularla) hasta que una persona resuelva el caso.
        tarjeta = GiftCard.objects.filter(purchase_order=order).first()
        if tarjeta is not None:
            with transaction.atomic():
                tarjetas_regalo.bloquear(tarjeta, f'Pago de la compra revertido por el proveedor: {motivo}')
    logger.error(
        'Pago revertido por el proveedor en el pedido %s (estado %s): %s',
        order.order_number, order.order_status, motivo,
    )


@transaction.atomic
def confirm_payment(order, payment_transaction):
    """Aplica el efecto de un pago aprobado: descuenta stock y confirma el
    pedido (ver `_confirmar_pedido_pagado`)."""
    if payment_transaction.status != 'approved':
        raise PaymentNotApprovedError()
    return _confirmar_pedido_pagado(order, nota='Pago aprobado.')


def _confirmar_pedido_pagado(order, nota):
    """Confirma un pedido ya pagado: por el proveedor (`confirm_payment`) o,
    sin nada que cobrar, por completo con una tarjeta de regalo.

    Idempotente por `order_status`: si el pedido ya quedo `confirmed` o
    `cancelled`, no vuelve a tocar nada (evita que un doble aviso de pago
    descuente stock dos veces). El pedido se bloquea antes de leer su estado,
    para que dos avisos simultaneos del proveedor no pasen la comprobacion a
    la vez.

    Si no hay stock suficiente en este momento (alguien mas compro la
    ultima unidad entre el checkout y la aprobacion), o si una variante ya
    no existe, el pedido no queda "confirmado a medias": se marca
    `cancelled` con una nota interna para revision humana. Un pago aprobado
    nunca se trata como si hubiera fallado en silencio.

    La compra de una tarjeta de regalo no descuenta stock, no genera comision
    ni factura: activa la tarjeta y se la envia a quien la recibe.
    """
    Order.objects.select_for_update().filter(pk=order.pk).first()
    order.refresh_from_db(fields=['order_status', 'payment_status', 'internal_note'])
    ahora = timezone.now()

    if order.order_status == OrderStatus.CONFIRMED:
        return order

    if order.order_status == OrderStatus.CANCELLED:
        if order.payment_status != PaymentStatus.APPROVED:
            # El pago llego despues de cancelar el pedido (por ejemplo, un
            # pago en efectivo que se acredita pasado el plazo): no se
            # reactiva, pero queda marcado para devolver el dinero.
            order.payment_status = PaymentStatus.APPROVED
            order.paid_at = ahora
            order.internal_note = _anotar(
                order.internal_note, 'Pago aprobado después de cancelar el pedido. Requiere reembolso manual.',
            )
            order.save(update_fields=['payment_status', 'paid_at', 'internal_note', 'updated_at'])
            enqueue(correos.pedido_cancelado, order.pk)
        return order

    estado_previo = order.order_status
    order.payment_status = PaymentStatus.APPROVED
    order.paid_at = ahora

    if order.is_gift_card_purchase:
        order.order_status = OrderStatus.CONFIRMED
        order.save(update_fields=['payment_status', 'paid_at', 'order_status', 'updated_at'])
        _registrar_estado(order, estado_previo, OrderStatus.CONFIRMED, nota=nota)
        tarjeta = tarjetas_regalo.activar_compra(order, ahora)
        if tarjeta is not None:
            enqueue(correos.tarjeta_regalo_para_destinatario, tarjeta.pk)
            enqueue(correos.tarjeta_regalo_comprada, order.pk)
        return order

    # Lo que se pago con tarjeta de regalo vuelve a la tarjeta si el pedido no
    # se puede cumplir; solo lo cobrado por el proveedor requiere reembolso.
    reembolso = 'Requiere reembolso manual.' if order.total > 0 else 'Lo pagado con tarjeta de regalo volvió a su saldo.'

    lineas = list(order.items.select_related('variant').all())
    lineas_sin_variante = [linea for linea in lineas if linea.variant_id is None]

    if lineas_sin_variante:
        skus = ', '.join(linea.sku_snapshot for linea in lineas_sin_variante)
        order.order_status = OrderStatus.CANCELLED
        order.cancelled_at = ahora
        order.internal_note = (
            f'Pago aprobado pero no se pudo descontar stock: variante(s) ya no '
            f'existen en el catálogo ({skus}). Requiere revisión manual.'
        )
        order.save(update_fields=[
            'payment_status', 'paid_at', 'order_status', 'cancelled_at', 'internal_note', 'updated_at',
        ])
        _registrar_estado(order, estado_previo, OrderStatus.CANCELLED, nota='Pago aprobado sin variante en el catálogo.')
        _liberar_lo_reservado(order, f'Pedido {order.order_number} cancelado: producto fuera del catálogo.')
        enqueue(correos.pedido_cancelado, order.pk)
        return order

    items = [(linea.variant, linea.quantity) for linea in lineas]

    try:
        decrement_stock(items)
    except InsufficientStockError as error:
        order.order_status = OrderStatus.CANCELLED
        order.cancelled_at = ahora
        order.internal_note = (
            f'Pago aprobado pero sin stock suficiente para {error.variant.sku} '
            f'(pedidas {error.requested}, disponibles {error.available}). '
            f'{reembolso}'
        )
        order.save(update_fields=[
            'payment_status', 'paid_at', 'order_status', 'cancelled_at', 'internal_note', 'updated_at',
        ])
        _registrar_estado(order, estado_previo, OrderStatus.CANCELLED, nota='Pago aprobado sin stock suficiente.')
        _liberar_lo_reservado(order, f'Pedido {order.order_number} cancelado: sin stock suficiente.')
        enqueue(correos.pedido_cancelado, order.pk)
        return order

    order.order_status = OrderStatus.CONFIRMED
    order.save(update_fields=['payment_status', 'paid_at', 'order_status', 'updated_at'])
    _registrar_estado(order, estado_previo, OrderStatus.CONFIRMED, nota=nota)
    if not order.is_test_order:
        # Un pedido de prueba no entro dinero: ni comision ni factura.
        pedido_cobrado.send(sender=Order, order=order)
        enqueue(facturacion.emitir_factura, order.pk)
    enqueue(correos.pedido_confirmado, order.pk)
    return order


@transaction.atomic
def confirmar_sin_pago(order, usuario):
    """Confirma un pedido sin cobrarlo: el modo de pruebas del panel para las
    cuentas del equipo (quien llama comprueba que aplique, ver
    `gotogym.ajustes_tienda.confirma_sin_pagar`).

    El pedido queda marcado como prueba (`is_test_order`) antes de
    confirmarse, para que no se facture ni genere comision, y con una nota
    de quien lo confirmo. Por lo demas sigue el camino de un pago aprobado:
    descuenta stock (se repone si se cancela) y, si es la compra de una
    tarjeta de regalo, la activa y la envia por correo."""
    pedido = Order.objects.select_for_update().get(pk=order.pk)
    if pedido.order_status != OrderStatus.PENDING_PAYMENT or pedido.payment_status == PaymentStatus.APPROVED:
        return pedido
    quien = getattr(usuario, 'email', '') or 'el equipo'
    pedido.is_test_order = True
    pedido.internal_note = _anotar(
        pedido.internal_note, f'Pedido de prueba: confirmado sin pago por {quien} (modo de pruebas del panel).',
    )
    pedido.save(update_fields=['is_test_order', 'internal_note', 'updated_at'])
    return _confirmar_pedido_pagado(pedido, nota=f'Confirmado sin pago (prueba) por {quien}.')
