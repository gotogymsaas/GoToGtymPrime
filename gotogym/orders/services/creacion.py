"""Creacion de pedidos a partir del carrito.

El pedido se crea antes de involucrar a ningun proveedor de pago, y todos
los importes se recalculan aqui desde la base de datos: nunca se confia en
un precio que venga de la sesion o del formulario.
"""
from decimal import Decimal

from carrito.services import build_cart_context
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import get_language, gettext
from gotogym.ajustes_tienda import MENSAJE_COMPRAS_PAUSADAS, compras_pausadas
from gotogym.tasks import enqueue
from inventory.services import get_available_quantity
from shipping.models import ShippingQuote
from shipping.services import get_mock_quote

from .. import correos, tarjetas_regalo
from ..models import (
    Address,
    Coupon,
    Order,
    OrderItem,
    OrderKind,
    OrderStatus,
    PaymentStatus,
)
from .cupones import get_usable_coupon
from .errores import CheckoutError, EmptyCartError, OutOfStockError
from .estados import _registrar_estado
from .pago import _confirmar_pedido_pagado

# Intentos para resolver la colision de dos pedidos creados a la vez.
MAX_INTENTOS_NUMERO = 5


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

    tarjeta = None
    if datos.get('gift_card_code'):
        tarjeta = tarjetas_regalo.buscar_tarjeta_usable(datos['gift_card_code'])
        if tarjeta is None:
            raise CheckoutError(gettext('La tarjeta de regalo ya no está disponible.'))

    if cupon is not None:
        # El uso se toma con un UPDATE condicional: `get_usable_coupon` leyo el
        # contador antes, y dos compras simultaneas verian ambas un cupo libre.
        # Si no actualiza ninguna fila, el cupon se agoto entre tanto y la
        # transaccion entera (incluido el pedido) se revierte.
        tomado = Coupon.objects.filter(pk=cupon.pk).filter(
            Q(max_uses__isnull=True) | Q(times_used__lt=F('max_uses')),
        ).update(times_used=F('times_used') + 1)
        if not tomado:
            raise CheckoutError(gettext('El cupón ya no está disponible.'))

    # El bucle asigna el pedido o relanza el error del ultimo intento.
    pedido: Order = None  # type: ignore[assignment]
    for intento in range(MAX_INTENTOS_NUMERO):
        try:
            with transaction.atomic():
                pedido = Order.objects.create(
                    user=user if getattr(user, 'is_authenticated', False) else None,
                    order_number=generate_order_number(),
                    language=get_language() or 'es',
                    email=datos['email'],
                    phone=datos['phone'],
                    customer_document_type=datos.get('document_type', ''),
                    customer_document_number=datos.get('document_number', ''),
                    subtotal=subtotal,
                    shipping_cost=envio,
                    discount_total=descuento,
                    total=total,
                    order_status=OrderStatus.PENDING_PAYMENT,
                    payment_status=PaymentStatus.PENDING,
                    referred_by=cupon.afiliado if cupon else None,
                    coupon=cupon,
                    gift_card=tarjeta,
                )
            break
        except IntegrityError:
            if intento == MAX_INTENTOS_NUMERO - 1:
                raise
            continue

    if tarjeta is not None:
        # La tarjeta paga despues del cupon y cubre tambien el envio. El saldo
        # se toma ya, con la tarjeta bloqueada; si el pedido no se paga, se
        # devuelve al cancelarse (ver `_liberar_lo_reservado`).
        try:
            pagado_con_tarjeta = tarjetas_regalo.canjear(tarjeta, pedido, total)
        except tarjetas_regalo.TarjetaNoDisponible:
            raise CheckoutError(gettext('La tarjeta de regalo ya no está disponible.')) from None
        pedido.gift_card_total = pagado_con_tarjeta
        pedido.total = total - pagado_con_tarjeta
        pedido.save(update_fields=['gift_card_total', 'total', 'updated_at'])

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

    if tarjeta is not None and pedido.total == 0:
        # Pagado por completo con tarjeta de regalo: no hay nada que cobrarle
        # al proveedor de pago, se confirma de una vez.
        _confirmar_pedido_pagado(pedido, nota='Pagado por completo con tarjeta de regalo.')
    else:
        enqueue(correos.pedido_recibido, pedido.pk)
    return pedido


@transaction.atomic
def create_gift_card_order(user, datos):
    """Crea la compra de una tarjeta de regalo: un pedido sin envio ni stock
    con una sola linea, y la tarjeta todavia sin activar. Se activa (y se le
    envia a quien la recibe) cuando el pago se aprueba.

    No acepta cupon ni otra tarjeta: una tarjeta se compra por su valor.
    `datos` trae `amount`, `sender_name`, `recipient_name`,
    `recipient_email` y `message`, ya validados por el formulario."""
    if compras_pausadas():
        raise CheckoutError(str(MENSAJE_COMPRAS_PAUSADAS))

    valor = Decimal(datos['amount']).quantize(Decimal('0.01'))
    if not tarjetas_regalo.VALOR_MINIMO <= valor <= tarjetas_regalo.VALOR_MAXIMO:
        raise CheckoutError(gettext('El valor de la tarjeta está fuera del rango permitido.'))

    idioma = get_language() or 'es'
    pedido: Order = None  # type: ignore[assignment]
    for intento in range(MAX_INTENTOS_NUMERO):
        try:
            with transaction.atomic():
                pedido = Order.objects.create(
                    kind=OrderKind.GIFT_CARD,
                    user=user if getattr(user, 'is_authenticated', False) else None,
                    order_number=generate_order_number(),
                    language=idioma,
                    email=user.email,
                    phone=getattr(user, 'phone', '') or '',
                    subtotal=valor,
                    shipping_cost=Decimal('0.00'),
                    discount_total=Decimal('0.00'),
                    total=valor,
                    order_status=OrderStatus.PENDING_PAYMENT,
                    payment_status=PaymentStatus.PENDING,
                )
            break
        except IntegrityError:
            if intento == MAX_INTENTOS_NUMERO - 1:
                raise
            continue

    OrderItem.objects.create(
        order=pedido,
        variant=None,
        product_name_snapshot=tarjetas_regalo.NOMBRE_TARJETA,
        sku_snapshot=tarjetas_regalo.SKU_TARJETA,
        size_snapshot='',
        color_snapshot='',
        unit_price_snapshot=valor,
        quantity=1,
        line_total=valor,
    )
    tarjetas_regalo.crear_tarjeta_pendiente(
        pedido, user, valor,
        remitente=datos['sender_name'],
        destinatario=datos['recipient_name'],
        correo=datos['recipient_email'],
        dedicatoria=datos.get('message', ''),
        idioma=idioma,
    )
    _registrar_estado(pedido, '', OrderStatus.PENDING_PAYMENT)
    enqueue(correos.pedido_recibido, pedido.pk)
    return pedido
