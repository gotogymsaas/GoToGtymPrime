"""Calculo del carrito, centralizado en el servidor.

El carrito de sesion guarda `{variant_id: cantidad}`. La variante es la
unidad vendible, asi que el precio y la disponibilidad se resuelven siempre
contra `ProductVariant`/`Inventory` y nunca contra un valor cacheado en la
sesion o enviado por el cliente.
"""
from decimal import Decimal

from products.models import ProductVariant
from shipping.services import get_mock_quote_estimate

SESSION_CART_KEY = 'cart'
SESSION_VERSION_KEY = 'cart_version'

# Se incrementa cuando cambia el significado de las claves del carrito. Un
# carrito guardado con una version distinta se descarta en vez de
# interpretarse mal: antes las claves eran ids de producto, no de variante, y
# ambos formatos son indistinguibles por su forma.
CART_VERSION = 2


def read_cart(session):
    """Devuelve `(carrito, se_reinicio)`.

    Si la sesion trae un carrito de una version anterior, se descarta y se
    informa para poder avisar al usuario.
    """
    cart = session.get(SESSION_CART_KEY) or {}
    if not cart:
        session[SESSION_VERSION_KEY] = CART_VERSION
        return {}, False

    if session.get(SESSION_VERSION_KEY) != CART_VERSION:
        session[SESSION_CART_KEY] = {}
        session[SESSION_VERSION_KEY] = CART_VERSION
        return {}, True

    return cart, False


def write_cart(session, cart):
    session[SESSION_CART_KEY] = cart
    session[SESSION_VERSION_KEY] = CART_VERSION


def cart_variants(cart):
    """Variantes del carrito, con producto e inventario ya resueltos."""
    ids = [key for key in cart if str(key).isdigit()]
    return (
        ProductVariant.objects
        .filter(id__in=ids, is_active=True)
        .select_related('product', 'product__category', 'inventory')
        .prefetch_related('product__media')
    )


def build_cart_context(cart):
    """Lineas y totales del carrito, calculados desde la base de datos.

    Es la unica funcion que debe usarse para calcular o mostrar el total.
    `shipping_estimate` es solo una estimacion (la tarifa mas baja posible):
    el carrito todavia no conoce la ciudad de entrega, asi que el envio no
    se suma al total mostrado aqui. El monto exacto se calcula y se congela
    recien en el checkout, cuando ya existe una direccion.
    """
    items = []
    subtotal = Decimal('0')

    variantes = sorted(
        cart_variants(cart),
        key=lambda v: (v.product.name, v.size, v.color),
    )

    for variante in variantes:
        cantidad = int(cart[str(variante.id)])
        if cantidad <= 0:
            continue
        precio = variante.effective_price
        item_subtotal = precio * cantidad
        items.append({
            'variant': variante,
            'producto': variante.product,
            'image': variante.product.primary_image,
            'cantidad': cantidad,
            'precio': precio,
            'subtotal': item_subtotal,
        })
        subtotal += item_subtotal

    return {
        'items': items,
        'subtotal': subtotal,
        'total': subtotal,
        'shipping_estimate': get_mock_quote_estimate(subtotal) if items else Decimal('0'),
        'num_items': sum(item['cantidad'] for item in items),
    }
