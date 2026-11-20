# Tarjetas de regalo

Tarjetas de regalo virtuales: alguien compra un saldo, escribe una dedicatoria y GoToGym se lo envía por correo a quien recibe el regalo, que lo usa al pagar en la tienda.

## Reglas del negocio

| Regla | Valor | Dónde está |
|---|---|---|
| Valor de la tarjeta | Entre $50.000 y $1.000.000 COP. Valores sugeridos: $50.000, $100.000, $200.000 y $500.000 | `orders/tarjetas_regalo.py` (`VALOR_MINIMO`, `VALOR_MAXIMO`, `VALORES_SUGERIDOS`) |
| Vigencia | 12 meses desde que se aprueba el pago, hasta las 23:59 (hora de Colombia) del mismo día un año después. Usar una parte no amplía el plazo | `MESES_DE_VIGENCIA`, `fecha_de_vencimiento` |
| Combinación | Se combina con un cupón: el cupón rebaja el precio primero y la tarjeta paga lo que queda, envío incluido | `create_order_from_cart` |
| Tarjetas por pedido | Una | Formulario del checkout |
| Cuenta | Comprar y canjear exige sesión | Vistas |
| PDF | El correo de regalo lleva adjunta la tarjeta en PDF (A5 horizontal, vectorial, con texto seleccionable), con la misma estética y la tipografía TT Norms. Si el PDF no se puede generar, el correo sale igual sin el adjunto | `orders/tarjeta_pdf.py`; fuentes en `orders/fuentes/` (`scripts/generar_fuentes_pdf.py`) |
| Dedicatoria | Hasta 300 caracteres, sin enlaces ni direcciones web | `GiftCardPurchaseForm` |
| Comisión de afiliados | Comprar una tarjeta no genera comisión. Un pedido pagado con tarjeta y hecho con código de afiliado sí, sobre el subtotal, como cualquier venta | La compra no admite cupón, así que no tiene afiliado |
| Retracto | 5 días hábiles desde la compra, solo si la tarjeta nunca se ha usado | `valid_next_statuses`, `puede_retractarse` |

El sustento legal (Circular Única de la SIC, numeral 2.18, y la doctrina de la DIAN sobre bonos) está en los términos y condiciones, cláusula «Tarjetas de regalo».

## Cómo funciona

1. **Compra** (`/tarjetas-regalo/`). Crea un pedido de tipo `gift_card`, sin dirección, envío ni stock, con una sola línea (`TARJETA-REGALO`), y una `GiftCard` en estado *pendiente de pago*. El código se genera desde ya, pero nadie lo ve. Al comprador le llega el aviso de compra recibida.
2. **Pago aprobado** (Mercado Pago, mismo flujo que cualquier pedido). El pedido queda *confirmado*, la tarjeta pasa a *activa* con su fecha de vencimiento, y salen dos correos: el de regalo al destinatario (con el código, el valor, la dedicatoria, cómo usarla y la vigencia) y la confirmación al comprador (sin el código completo). No se factura ni genera comisión.
3. **Canje.** En el checkout hay un solo campo, «Cupón o tarjeta de regalo»: el sistema detecta qué es cada código y lo deja aplicado como una etiqueta que se puede quitar, así que un pedido puede llevar un cupón y una tarjeta. La tarjeta muestra su saldo y cuánto cubre. Al confirmar el pedido, el saldo se toma con la tarjeta bloqueada en la base, para que dos compras simultáneas no gasten el mismo dinero. Si la tarjeta cubre todo, el pedido se confirma sin pasar por Mercado Pago.
4. **Cancelación o devolución** del pedido en que se usó: lo pagado con la tarjeta vuelve a su saldo automáticamente. Lo cobrado por Mercado Pago se reembolsa como siempre, desde el panel.

Cada cambio de saldo queda en `GiftCardMovement` (emisión, canje, devolución de saldo, anulación), con el pedido que lo causó.

En el pedido, `total` es lo que cobra Mercado Pago y `gift_card_total` lo pagado con la tarjeta. Lo pagado con tarjeta **no es un descuento**: la factura del canje sale por el valor completo (ver [FACTURACION_ALEGRA.md](FACTURACION_ALEGRA.md)).

## Operación desde el panel

**Tarjetas de regalo** (menú del panel) muestra:

- **Saldo por canjear (vigente).** Dinero recibido por mercancía que todavía no se entrega: es un pasivo, no un ingreso. Es el dato que necesita el contador.
- **Vendido**, **saldo vencido sin usar** y **activas sin correo enviado** (si el envío falló).
- La lista se busca por los últimos 4 caracteres del código, por correo o por número de pedido.

En el detalle de cada tarjeta:

- **Bloquear / desbloquear.** Impide canjearla sin tocar el saldo, mientras se resuelve un reclamo o una sospecha de fraude.
- **Reenviar el correo.** Si el comprador escribió mal el correo del destinatario, se corrige ahí y se reenvía. Confirma el cambio con quien compró.
- **Código completo.** Visible solo para quien puede editar pedidos. Es de quien recibe el regalo: no se le da a nadie más.

### Retracto (devolver la compra de una tarjeta)

Si la tarjeta nunca se ha usado, el detalle del pedido de compra permite pasarlo a *Cancelado*. La tarjeta queda anulada y al cliente le llega el aviso. Después se reembolsa el pago con el botón de siempre. Si la tarjeta ya se usó, aunque sea en un pedido que luego se canceló, el panel no ofrece la cancelación.

### Contracargo de la compra

Si Mercado Pago revierte el pago de una compra de tarjeta, la tarjeta se bloquea sola (con el motivo anotado) y el pedido queda anotado como cualquier contracargo. Una persona decide si la desbloquea o la anula.

## Probar sin pagar: modo de pruebas del equipo

En la barra superior del panel está el interruptor **«Confirmar sin pagar (equipo)»**. Pide confirmación al encenderlo y, mientras esté encendido, el panel muestra un aviso dorado.

- **A quién aplica.** Solo a las cuentas del equipo (las que entran al panel). Los clientes siguen pagando normal aunque esté encendido.
- **Qué hace.** Al confirmar el checkout o comprar una tarjeta de regalo, en vez de ir a Mercado Pago el pedido se confirma. Un pedido que había quedado pendiente se confirma al pulsar «Confirmar sin pagar (prueba)» en su detalle.
- **Cómo queda el pedido.** Marcado como «Prueba sin pago» (`Order.is_test_order`), con una nota de quién lo confirmó. No se factura, no genera comisión y no cuenta en las ventas del panel. La exportación CSV lo trae con `prueba_sin_pago = si`.
- **Qué sí pasa de verdad.** Descuenta stock (se repone si cancelas el pedido) y las tarjetas de regalo se activan, se envían por correo y se pueden canjear. Las tarjetas de prueba no suman al saldo por canjear del panel.
- **Apágalo al terminar.** Cancela los pedidos de prueba de productos que no necesites, para devolver el stock.

## Métricas

Las compras de tarjetas no cuentan como ventas en la analítica del panel, porque la venta ocurre cuando la tarjeta se canjea, igual que en la factura. Se ven en el panel de tarjetas. La exportación CSV de pedidos sí las incluye, con la columna `tipo = gift_card`, y agrega la columna `tarjeta_regalo` con lo pagado con tarjeta.

## Dependencias

- `reportlab==5.1.0` (en `requirements.txt`) dibuja el PDF. Se instala sola en el despliegue.
- Las fuentes del PDF están en `gotogym/orders/fuentes/`. Si cambia la tipografía, se regeneran con `python scripts/generar_fuentes_pdf.py` (necesita `fontTools`, solo en el equipo de quien la regenera).
- `pypdf`, que ya estaba, lo usan las pruebas para comprobar que el código del PDF se puede copiar como texto.

## Pendiente o por decidir

- **Contador:** cuál es el medio de pago de Alegra para un pedido pagado por completo con tarjeta (`ALEGRA_MEDIO_DE_PAGO_TARJETA_REGALO`) y el tratamiento contable del saldo que vence sin usarse.
- **Envío programado** (por ejemplo, que el regalo llegue el día del cumpleaños): necesita un programador de tareas desplegado, que hoy no existe.
- **Varios diseños de tarjeta.**
