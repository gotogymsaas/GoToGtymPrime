"""Estado logistico de un pedido: transiciones validas, historial y lo que
cada cambio arrastra (stock, cupon, tarjeta de regalo, envio, correos)."""
from django.db import transaction
from django.utils import timezone
from gotogym.tasks import enqueue
from inventory.services import restore_stock
from shipping.models import ShippingQuote, ShippingStatus

from .. import correos, tarjetas_regalo
from ..models import Order, OrderStatus, OrderStatusHistory, PaymentStatus
from ..senales import pedido_anulado, pedido_entregado
from .cupones import release_coupon
from .errores import InvalidOrderTransitionError


def _anotar(nota_actual, texto):
    """Agrega `texto` a la nota interna sin pisar lo que ya tenia."""
    return f'{nota_actual}\n{texto}' if nota_actual else texto


def _liberar_lo_reservado(order, nota):
    """Deshace lo que un pedido que no se concreto tenia tomado: el uso del
    cupon, el saldo de la tarjeta de regalo con que se pagaba y, si era la
    compra de una tarjeta, la tarjeta misma."""
    release_coupon(order)
    tarjetas_regalo.devolver_saldo(order, nota)
    if order.is_gift_card_purchase:
        tarjetas_regalo.anular_compra(order, nota)


# Estado del envio que corresponde a cada estado logistico del pedido.
_ESTADO_DE_ENVIO = {
    OrderStatus.SHIPPED: ShippingStatus.SHIPPED,
    OrderStatus.IN_TRANSIT: ShippingStatus.IN_TRANSIT,
    OrderStatus.DELIVERED: ShippingStatus.DELIVERED,
    OrderStatus.RETURNED: ShippingStatus.RETURNED,
    OrderStatus.CANCELLED: ShippingStatus.CANCELLED,
}


def _registrar_estado(order, desde, hasta, changed_by=None, nota=''):
    """Deja constancia de un cambio de estado y mantiene al dia lo que
    depende de el: el estado de la cotizacion de envio."""
    OrderStatusHistory.objects.create(
        order=order, from_status=desde or '', to_status=hasta,
        changed_by=changed_by if getattr(changed_by, 'is_authenticated', False) else None,
        note=nota[:255],
    )
    estado_envio = _ESTADO_DE_ENVIO.get(hasta)
    if estado_envio:
        ShippingQuote.objects.filter(order=order).update(shipping_status=estado_envio)


def _reponer_stock(order):
    """Devuelve al inventario las unidades de un pedido cuyo stock ya se
    descontó. Las lineas cuya variante ya no existe se omiten: no hay donde
    reponerlas."""
    items = [
        (linea.variant, linea.quantity)
        for linea in order.items.select_related('variant').all()
        if linea.variant_id is not None
    ]
    restore_stock(items)


# Secuencia logistica del pedido. `confirmed` solo se alcanza si el pago ya
# esta aprobado (ver `valid_next_statuses`). Desde cualquier estado se puede
# saltar a cualquier estado *posterior* de la secuencia (no solo al
# inmediato siguiente): en la operacion real, quien actualiza el pedido a
# veces se entera del estado final directo (por ejemplo, la transportadora
# avisa "entregado" sin que nadie haya marcado antes "en transito"), y
# obligar a pasar por cada paso intermedio uno por uno no refleja eso.
# Lo que si sigue sin poder pasar es retroceder o saltarse `confirmed` sin
# pago aprobado.
ORDER_STATUS_SEQUENCE = [
    OrderStatus.PENDING_PAYMENT,
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARING,
    OrderStatus.SHIPPED,
    OrderStatus.IN_TRANSIT,
    OrderStatus.DELIVERED,
]

# Desde que estados es valido cancelar. Una vez enviado, cancelar ya no es
# una operacion de estado (el paquete existe fisicamente en transito).
CANCELLABLE_FROM = {OrderStatus.PENDING_PAYMENT, OrderStatus.CONFIRMED, OrderStatus.PREPARING}

# Una devolucion solo tiene sentido una vez el paquete salio (o llego): no
# se "devuelve" algo que todavia esta en preparacion, eso se cancela.
RETURNABLE_FROM = {OrderStatus.SHIPPED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED}


def valid_next_statuses(order):
    """Estados a los que un pedido puede pasar desde el estado actual.

    Permite avanzar a cualquier paso posterior de la secuencia logistica
    (no solo al inmediato siguiente), mas cancelar o marcar devolucion
    cuando el estado actual lo permite. La unica puerta real es
    `confirmed`: si el pago todavia no esta aprobado, nada que venga
    despues de `confirmed` en la secuencia es alcanzable tampoco, aunque
    el salto sea directo (saltarse el paso no se salta el requisito).
    """
    if order.order_status not in ORDER_STATUS_SEQUENCE:
        return []

    if order.is_gift_card_purchase:
        # La compra de una tarjeta no tiene logistica: solo se cancela. Sin
        # pago, siempre; ya pagada (retracto), solo si la tarjeta nunca se
        # ha canjeado, porque ese saldo ya no se puede recuperar.
        if order.order_status == OrderStatus.PENDING_PAYMENT:
            return [OrderStatus.CANCELLED]
        if order.order_status == OrderStatus.CONFIRMED and tarjetas_regalo.puede_retractarse(order):
            return [OrderStatus.CANCELLED]
        return []

    indice = ORDER_STATUS_SEQUENCE.index(order.order_status)
    restantes = ORDER_STATUS_SEQUENCE[indice + 1:]

    if OrderStatus.CONFIRMED in restantes and order.payment_status != PaymentStatus.APPROVED:
        siguientes = []
    else:
        siguientes = list(restantes)

    if order.order_status in CANCELLABLE_FROM:
        siguientes.append(OrderStatus.CANCELLED)

    if order.order_status in RETURNABLE_FROM:
        siguientes.append(OrderStatus.RETURNED)

    return siguientes


def set_tracking_code(order, codigo):
    """Guarda la guia de envio del pedido (vacia la borra).

    Devuelve False si el pedido no tiene cotizacion de envio donde guardarla.
    """
    longitud = ShippingQuote._meta.get_field('tracking_code').max_length
    codigo = ' '.join((codigo or '').split())[:longitud]
    actualizadas = ShippingQuote.objects.filter(order=order).update(tracking_code=codigo)
    return bool(actualizadas)


@transaction.atomic
def apply_order_status_transition(order, nuevo_estado, tracking_code=None, changed_by=None):
    """Mueve `order_status` un paso valido hacia adelante (o a cancelado).

    Nunca toca `payment_status`: ese campo lo controla exclusivamente el
    proveedor de pago via `confirm_payment`, nunca una accion de admin.

    `tracking_code` se guarda en la misma operacion, de modo que el correo de
    envio, que se arma despues de confirmar la transaccion, ya la incluya.
    """
    # Se relee el pedido con la fila bloqueada: la instancia que llega pudo
    # leerse antes de que otra operacion (por ejemplo la confirmacion del pago)
    # cambiara el estado, y validar la transicion sobre ese estado viejo
    # cancelaria un pedido ya confirmado sin devolver su stock.
    Order.objects.select_for_update().only('pk').get(pk=order.pk)
    order.refresh_from_db()
    if nuevo_estado not in valid_next_statuses(order):
        raise InvalidOrderTransitionError(order, nuevo_estado)

    if tracking_code and nuevo_estado in (OrderStatus.SHIPPED, OrderStatus.IN_TRANSIT):
        set_tracking_code(order, tracking_code)

    estado_anterior = order.order_status
    order.order_status = nuevo_estado
    campos = ['order_status', 'updated_at']
    ahora = timezone.now()
    if nuevo_estado == OrderStatus.DELIVERED:
        order.delivered_at = ahora
        campos.append('delivered_at')
    if nuevo_estado in (OrderStatus.SHIPPED, OrderStatus.IN_TRANSIT) and order.shipped_at is None:
        order.shipped_at = ahora
        campos.append('shipped_at')
    if nuevo_estado == OrderStatus.CANCELLED:
        order.cancelled_at = ahora
        campos.append('cancelled_at')
    order.save(update_fields=campos)
    _registrar_estado(order, estado_anterior, nuevo_estado, changed_by=changed_by)

    # El stock se descuenta al confirmar el pago: un pedido que ya paso por
    # `confirmed` lo tiene descontado y debe devolverlo al cancelarse o
    # devolverse. Uno cancelado desde `pending_payment` nunca lo descontó.
    if nuevo_estado in (OrderStatus.CANCELLED, OrderStatus.RETURNED) and estado_anterior != OrderStatus.PENDING_PAYMENT:
        _reponer_stock(order)

    # Efecto sobre la comision del afiliado, si el pedido tiene una: al
    # entregarse empieza su periodo de validacion (el plazo de devolucion del
    # cliente) y se revierte si el pedido se cancela o se devuelve. No hace
    # nada si el pedido no esta referido o no tiene comision todavia.
    if nuevo_estado == OrderStatus.DELIVERED:
        pedido_entregado.send(sender=Order, order=order)
    elif nuevo_estado in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
        pedido_anulado.send(sender=Order, order=order)

    if nuevo_estado == OrderStatus.SHIPPED:
        enqueue(correos.pedido_enviado, order.pk)
    elif nuevo_estado == OrderStatus.CANCELLED:
        _liberar_lo_reservado(order, f'Pedido {order.order_number} cancelado.')
        enqueue(correos.pedido_cancelado, order.pk)
    elif nuevo_estado == OrderStatus.RETURNED:
        # Lo pagado con tarjeta de regalo se devuelve a la tarjeta; lo cobrado
        # por el proveedor se reembolsa aparte, desde el panel.
        tarjetas_regalo.devolver_saldo(order, f'Pedido {order.order_number} devuelto.', changed_by)

    return order
