"""Creacion de pedidos a partir del carrito.

El pedido se crea antes de involucrar a ningun proveedor de pago, y todos
los importes se recalculan aqui desde la base de datos: nunca se confia en
un precio que venga de la sesion o del formulario.
"""
from decimal import Decimal

from carrito.services import build_cart_context
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from inventory.services import InsufficientStockError, decrement_stock, get_available_quantity
from shipping.models import ShippingQuote
from shipping.services import get_mock_quote

from .models import Address, Coupon, Order, OrderItem, OrderStatus, PaymentStatus

# Intentos para resolver la colision de dos pedidos creados a la vez.
MAX_INTENTOS_NUMERO = 5


def get_usable_coupon(coupon_code):
    """Busca un cupon utilizable por su codigo, o None si no aplica.

    Centraliza la busqueda para que el formulario (validacion) y el
    servicio de creacion del pedido (aplicacion real) usen exactamente el
    mismo criterio de "utilizable".
    """
    codigo = (coupon_code or '').strip().upper()
    if not codigo:
        return None
    cupon = Coupon.objects.filter(code=codigo).first()
    if cupon is None or not cupon.is_usable():
        return None
    return cupon


def calculate_coupon_discount(subtotal, coupon_code=''):
    """Calcula el descuento del cupon indicado, si existe y es utilizable."""
    cupon = get_usable_coupon(coupon_code)
    if cupon is None:
        return Decimal('0.00')
    return cupon.compute_discount(subtotal)


class CheckoutError(Exception):
    """Error de negocio que impide crear el pedido."""


class EmptyCartError(CheckoutError):
    def __init__(self):
        super().__init__('Tu carrito esta vacio.')


class OutOfStockError(CheckoutError):
    def __init__(self, faltantes):
        self.faltantes = faltantes
        detalle = '; '.join(
            f"{sku}: pediste {pedido}, quedan {disponible}"
            for sku, pedido, disponible in faltantes
        )
        super().__init__(f'No hay unidades suficientes. {detalle}')


class PaymentNotApprovedError(CheckoutError):
    def __init__(self):
        super().__init__('El pago todavia no esta aprobado.')


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


def apply_order_status_transition(order, nuevo_estado):
    """Mueve `order_status` un paso valido hacia adelante (o a cancelado).

    Nunca toca `payment_status`: ese campo lo controla exclusivamente el
    proveedor de pago via `confirm_payment`, nunca una accion de admin.
    """
    if nuevo_estado not in valid_next_statuses(order):
        raise InvalidOrderTransitionError(order, nuevo_estado)

    order.order_status = nuevo_estado
    order.save(update_fields=['order_status', 'updated_at'])
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
    contexto = build_cart_context(cart)
    items = contexto['items']

    if not items:
        raise EmptyCartError()

    _validar_disponibilidad(items)

    subtotal = Decimal(contexto['subtotal']).quantize(Decimal('0.01'))
    cotizacion = get_mock_quote(datos['city'], subtotal)
    envio = Decimal(cotizacion['cost']).quantize(Decimal('0.01'))
    cupon = get_usable_coupon(datos.get('coupon_code', ''))
    descuento = cupon.compute_discount(subtotal) if cupon else Decimal('0.00')
    total = subtotal + envio - descuento

    pedido = None
    for intento in range(MAX_INTENTOS_NUMERO):
        try:
            with transaction.atomic():
                pedido = Order.objects.create(
                    user=user if getattr(user, 'is_authenticated', False) else None,
                    order_number=generate_order_number(),
                    email=datos['email'],
                    phone=datos['phone'],
                    subtotal=subtotal,
                    shipping_cost=envio,
                    discount_total=descuento,
                    total=total,
                    order_status=OrderStatus.PENDING_PAYMENT,
                    payment_status=PaymentStatus.PENDING,
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

    return pedido


@transaction.atomic
def confirm_payment(order, payment_transaction):
    """Aplica el efecto de un pago aprobado: descuenta stock y confirma el
    pedido.

    Idempotente por `order_status`: si el pedido ya quedo `confirmed` o
    `cancelled`, no vuelve a tocar nada (evita que un doble aviso de pago
    descuente stock dos veces).

    Si no hay stock suficiente en este momento (alguien mas compro la
    ultima unidad entre el checkout y la aprobacion), o si una variante ya
    no existe, el pedido no queda "confirmado a medias": se marca
    `cancelled` con una nota interna para revision humana. Un pago aprobado
    nunca se trata como si hubiera fallado en silencio.
    """
    if payment_transaction.status != 'approved':
        raise PaymentNotApprovedError()

    if order.order_status in (OrderStatus.CONFIRMED, OrderStatus.CANCELLED):
        return order

    order.payment_status = PaymentStatus.APPROVED

    lineas = list(order.items.select_related('variant').all())
    lineas_sin_variante = [linea for linea in lineas if linea.variant_id is None]

    if lineas_sin_variante:
        skus = ', '.join(linea.sku_snapshot for linea in lineas_sin_variante)
        order.order_status = OrderStatus.CANCELLED
        order.internal_note = (
            f'Pago aprobado pero no se pudo descontar stock: variante(s) ya no '
            f'existen en el catalogo ({skus}). Requiere revision manual.'
        )
        order.save(update_fields=['payment_status', 'order_status', 'internal_note', 'updated_at'])
        return order

    items = [(linea.variant, linea.quantity) for linea in lineas]

    try:
        decrement_stock(items)
    except InsufficientStockError as error:
        order.order_status = OrderStatus.CANCELLED
        order.internal_note = (
            f'Pago aprobado pero sin stock suficiente para {error.variant.sku} '
            f'(pedidas {error.requested}, disponibles {error.available}). '
            f'Requiere reembolso manual.'
        )
        order.save(update_fields=['payment_status', 'order_status', 'internal_note', 'updated_at'])
        return order

    order.order_status = OrderStatus.CONFIRMED
    order.save(update_fields=['payment_status', 'order_status', 'updated_at'])
    return order
