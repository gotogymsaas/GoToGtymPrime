"""Hechos del ciclo de vida de un pedido que otras apps pueden escuchar.

`orders` esta por debajo de las apps que reaccionan a sus pedidos (por
ejemplo `afiliados`, que paga comision por ellos), asi que no las importa: las
avisa con estas senales y cada una conecta sus receptores en su `ready()`.

Las senales se envian con `send` (no `send_robust`), en el mismo hilo y dentro
de la misma transaccion que el cambio que anuncian, justo en el punto donde
ocurre. Un receptor que lanza una excepcion la propaga a quien cambio el
pedido y revierte la transaccion, igual que si el efecto estuviera escrito en
la propia funcion. Los receptores no deben usar `on_commit`.

Todas se envian con `sender=Order` y el pedido como argumento `order`.
"""
from django.dispatch import Signal

# El pago se aprobo y el pedido quedo confirmado con dinero real: no se emite
# para los pedidos de prueba, la compra de una tarjeta de regalo ni un pedido
# que se cancela al confirmar (sin stock o sin variante).
pedido_cobrado = Signal()

# El pedido paso a `delivered`.
pedido_entregado = Signal()

# El pedido ya no va a concretarse: se cancelo o se devolvio (`motivo` no
# viaja), o el proveedor de pago revirtio el cobro (`motivo` explica por que).
pedido_anulado = Signal()
