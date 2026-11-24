"""Lo que el programa de afiliados hace cuando cambia un pedido.

`orders` avisa con senales (ver `orders.senales`) y estos receptores aplican el
efecto sobre la comision del pedido. Se conectan en `AfiliadosConfig.ready`.
Corren sincronos y dentro de la transaccion del cambio, sin tomar nada de la
senal salvo el pedido: no usan `on_commit`.
"""
from .services import (
    register_order_commission,
    revert_order_commission,
    schedule_order_commission_validation,
)


def registrar_comision(sender, order, **kwargs):
    """El pago del pedido quedo aprobado: nace su comision pendiente."""
    register_order_commission(order)


def iniciar_validacion_de_comision(sender, order, **kwargs):
    """El pedido se entrego: empieza el plazo de devolucion del cliente."""
    schedule_order_commission_validation(order)


def revertir_comision(sender, order, motivo=None, **kwargs):
    """El pedido se cancelo, se devolvio o se revirtio su pago. Sin `motivo`
    se usa el que `revert_order_commission` trae por defecto."""
    if motivo is None:
        revert_order_commission(order)
    else:
        revert_order_commission(order, motivo)
