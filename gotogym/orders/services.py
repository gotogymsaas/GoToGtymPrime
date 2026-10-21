"""Creacion de pedidos a partir del carrito.

El pedido se crea antes de involucrar a ningun proveedor de pago, y todos
los importes se recalculan aqui desde la base de datos: nunca se confia en
un precio que venga de la sesion o del formulario.
"""
from datetime import timedelta
from decimal import Decimal

from afiliados.services import (
    afiliado_operativo,
    register_order_commission,
    revert_order_commission,
    schedule_order_commission_validation,
)
from carrito.services import build_cart_context
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import get_language, gettext
from gotogym.ajustes_tienda import MENSAJE_COMPRAS_PAUSADAS, compras_pausadas
from gotogym.tasks import enqueue
from inventory.services import (
    InsufficientStockError,
    decrement_stock,
    get_available_quantity,
    restore_stock,
)
from shipping.models import ShippingQuote, ShippingStatus
from shipping.services import get_mock_quote

from . import correos
from .models import (
    Address,
    Coupon,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentStatus,
)

# Intentos para resolver la colision de dos pedidos creados a la vez.
MAX_INTENTOS_NUMERO = 5


def get_usable_coupon(coupon_code, user=None):
    """Busca un cupon utilizable por su codigo, o None si no aplica.

    Centraliza la busqueda para que el formulario (validacion) y el
    servicio de creacion del pedido (aplicacion real) usen exactamente el
    mismo criterio de "utilizable". Si `user` es el propio afiliado dueño
    del cupon, se trata como no utilizable: control de autorreferencia
    (RF-F11), para que nadie se autoaplique el descuento ni se genere
    comision sobre su propia compra.
    """
    codigo = (coupon_code or '').strip().upper()
    if not codigo:
        return None
    cupon = Coupon.objects.filter(code=codigo).select_related('afiliado').first()
    if cupon is None or not cupon.is_usable():
        return None
    # Un afiliado cuyo preaviso de baja ya vencio deja de aceptarse aunque la
    # baja todavia no se haya aplicado en la base.
    if cupon.afiliado_id and not afiliado_operativo(cupon.afiliado):
        return None
    autenticado = user is not None and getattr(user, 'is_authenticated', False)
    if cupon.afiliado_id and autenticado and cupon.afiliado.user_id == user.id:
        return None
    if cupon.customer_segment_id:
        # Cupon restringido a un segmento de cliente (p. ej. entrenadores,
        # clubes): sin sesion o fuera del segmento, se trata como no
        # utilizable, igual que un cupon vencido.
        if not autenticado or not user.customer_segments.filter(pk=cupon.customer_segment_id).exists():
            return None
    return cupon


def es_cupon_propio(coupon_code, user):
    """Si el codigo es el cupon personal del afiliado que esta comprando.

    `get_usable_coupon` lo rechaza igual que a uno inexistente; esto permite
    decirle a la persona por que, en vez de un "no valido" que la hace creer
    que su codigo esta roto."""
    codigo = (coupon_code or '').strip().upper()
    if not codigo or user is None or not getattr(user, 'is_authenticated', False):
        return False
    return Coupon.objects.filter(code=codigo, afiliado__user=user).exists()


def _anotar(nota_actual, texto):
    """Agrega `texto` a la nota interna sin pisar lo que ya tenia."""
    return f'{nota_actual}\n{texto}' if nota_actual else texto


def release_coupon(order):
    """Devuelve el uso del cupon de un pedido que no se concreto.

    Se llama una sola vez, al pasar el pedido a `cancelled` (un estado final:
    no se vuelve a salir de el). Sin esto, los pedidos abandonados o con el
    pago rechazado agotarian los cupones de uso limitado."""
    if order.coupon_id:
        Coupon.objects.filter(pk=order.coupon_id, times_used__gt=0).update(times_used=F('times_used') - 1)


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
        schedule_order_commission_validation(order)
    elif nuevo_estado in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
        revert_order_commission(order)

    if nuevo_estado == OrderStatus.SHIPPED:
        enqueue(correos.pedido_enviado, order.pk)
    elif nuevo_estado == OrderStatus.CANCELLED:
        release_coupon(order)
        enqueue(correos.pedido_cancelado, order.pk)

    return order


def generate_order_number(momento=None):
    """Numero legible y unico: GTG-AAAAMM-0001."""
    momento = momento or timezone.now()
    prefijo = f"GTG-{momento:%Y%m}"
    ultimo = (
        Order.objects
        .filter(order_number__startswith=prefijo)
        .order_by('-order_number')
        .values_list('order_number', flat=True)
        .first()
    )
    siguiente = 1
    if ultimo:
        try:
            siguiente = int(ultimo.rsplit('-', 1)[1]) + 1
        except (IndexError, ValueError):
            siguiente = Order.objects.filter(order_number__startswith=prefijo).count() + 1
    return f"{prefijo}-{siguiente:04d}"


def _validar_disponibilidad(items):
    """Comprobacion optimista, sin bloqueo.

    Da buen mensaje al usuario en el momento del checkout, pero no garantiza
    nada frente a otra compra simultanea: la verificacion que decide ocurre
    al confirmar el pago, donde el stock se descuenta con bloqueo.
    """
    faltantes = []
    for item in items:
        disponible = get_available_quantity(item['variant'])
        if item['cantidad'] > disponible:
            faltantes.append((item['variant'].sku, item['cantidad'], disponible))
    if faltantes:
        raise OutOfStockError(faltantes)


@transaction.atomic
def create_order_from_cart(user, cart, datos):
    """Crea el pedido, sus lineas y la direccion en una sola transaccion.

    Devuelve la `Order` creada. Si algo falla no queda nada a medias.
    """
    # Ultima barrera: la vista ya redirige, pero un POST directo o una
    # pestana abierta antes de la pausa llegan hasta aqui.
    if compras_pausadas():
        raise CheckoutError(str(MENSAJE_COMPRAS_PAUSADAS))

    contexto = build_cart_context(cart)
    items = contexto['items']

    if not items:
        raise EmptyCartError()

    _validar_disponibilidad(items)

    subtotal = Decimal(contexto['subtotal']).quantize(Decimal('0.01'))
    cotizacion = get_mock_quote(datos['city'], subtotal)
    envio = Decimal(cotizacion['cost']).quantize(Decimal('0.01'))
    cupon = get_usable_coupon(datos.get('coupon_code', ''), user=user)
    descuento = cupon.compute_discount(subtotal) if cupon else Decimal('0.00')
    total = subtotal + envio - descuento

    pedido = None
    for intento in range(MAX_INTENTOS_NUMERO):
        try:
            with transaction.atomic():
                pedido = Order.objects.create(
                    user=user if getattr(user, 'is_authenticated', False) else None,
                    order_number=generate_order_number(),
                    language=get_language() or 'es',
                    email=datos['email'],
                    phone=datos['phone'],
                    subtotal=subtotal,
                    shipping_cost=envio,
                    discount_total=descuento,
                    total=total,
                    order_status=OrderStatus.PENDING_PAYMENT,
                    payment_status=PaymentStatus.PENDING,
                    referred_by=cupon.afiliado if cupon else None,
                    coupon=cupon,
                )
            break
        except IntegrityError:
            if intento == MAX_INTENTOS_NUMERO - 1:
                raise
            continue

    if cupon is not None:
        Coupon.objects.filter(pk=cupon.pk).update(times_used=F('times_used') + 1)

    for item in items:
        variante = item['variant']
        precio = Decimal(item['precio']).quantize(Decimal('0.01'))
        OrderItem.objects.create(
            order=pedido,
            variant=variante,
            product_name_snapshot=variante.product.name,
            sku_snapshot=variante.sku,
            size_snapshot=variante.size,
            color_snapshot=variante.color,
            unit_price_snapshot=precio,
            quantity=item['cantidad'],
            line_total=(precio * item['cantidad']).quantize(Decimal('0.01')),
        )

    _registrar_estado(pedido, '', OrderStatus.PENDING_PAYMENT)

    Address.objects.create(
        order=pedido,
        full_name=f"{datos['first_name']} {datos['last_name']}".strip(),
        phone=datos['phone'],
        country=datos['country'],
        department=datos['department'],
        city=datos['city'],
        postal_code=datos.get('postal_code', ''),
        address_line=datos['address_line'],
        address_complement=datos.get('address_complement', ''),
        notes=datos.get('notes', ''),
    )

    ShippingQuote.objects.create(
        order=pedido,
        carrier_name=cotizacion['carrier_name'],
        method_name=cotizacion['method_name'],
        cost=envio,
        estimated_days=cotizacion['estimated_days'],
    )

    enqueue(correos.pedido_recibido, pedido.pk)
    return pedido


@transaction.atomic
def confirm_payment(order, payment_transaction):
    """Aplica el efecto de un pago aprobado: descuenta stock y confirma el
    pedido.

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
    """
    if payment_transaction.status != 'approved':
        raise PaymentNotApprovedError()

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
        release_coupon(order)
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
            f'Requiere reembolso manual.'
        )
        order.save(update_fields=[
            'payment_status', 'paid_at', 'order_status', 'cancelled_at', 'internal_note', 'updated_at',
        ])
        _registrar_estado(order, estado_previo, OrderStatus.CANCELLED, nota='Pago aprobado sin stock suficiente.')
        release_coupon(order)
        enqueue(correos.pedido_cancelado, order.pk)
        return order

    order.order_status = OrderStatus.CONFIRMED
    order.save(update_fields=['payment_status', 'paid_at', 'order_status', 'updated_at'])
    _registrar_estado(order, estado_previo, OrderStatus.CONFIRMED, nota='Pago aprobado.')
    register_order_commission(order)
    enqueue(correos.pedido_confirmado, order.pk)
    return order


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
            release_coupon(pedido)
            enqueue(correos.pedido_cancelado, pedido.pk)
            canceladas += 1
    return canceladas
