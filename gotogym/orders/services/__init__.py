"""Servicios de pedidos: creacion desde el carrito, transiciones de estado,
efecto del pago y vencimiento de los no pagados.

Cada modulo cubre una etapa; este paquete reexporta los nombres publicos para
que el resto del codigo siga importando desde `orders.services`. Las pruebas
que sustituyen una funcion apuntan al modulo donde se usa (por ejemplo
`orders.services.creacion.get_usable_coupon`).

Los efectos sobre otras apps (la comision del afiliado) no se llaman desde
aqui: se emiten como senales (ver `orders.senales`).
"""
from .creacion import (
    MAX_INTENTOS_NUMERO,
    create_gift_card_order,
    create_order_from_cart,
    generate_order_number,
)
from .cupones import es_cupon_propio, get_usable_coupon, release_coupon
from .errores import (
    CheckoutError,
    EmptyCartError,
    InvalidOrderTransitionError,
    OutOfStockError,
    PaymentNotApprovedError,
)
from .estados import (
    CANCELLABLE_FROM,
    ORDER_STATUS_SEQUENCE,
    RETURNABLE_FROM,
    apply_order_status_transition,
    set_tracking_code,
    valid_next_statuses,
)
from .pago import (
    confirm_payment,
    confirmar_sin_pago,
    registrar_pago_revertido,
)
from .vencimiento import cancel_expired_orders

__all__ = [
    'CANCELLABLE_FROM',
    'MAX_INTENTOS_NUMERO',
    'ORDER_STATUS_SEQUENCE',
    'RETURNABLE_FROM',
    'CheckoutError',
    'EmptyCartError',
    'InvalidOrderTransitionError',
    'OutOfStockError',
    'PaymentNotApprovedError',
    'apply_order_status_transition',
    'cancel_expired_orders',
    'confirm_payment',
    'confirmar_sin_pago',
    'create_gift_card_order',
    'create_order_from_cart',
    'es_cupon_propio',
    'generate_order_number',
    'get_usable_coupon',
    'registrar_pago_revertido',
    'release_coupon',
    'set_tracking_code',
    'valid_next_statuses',
]
