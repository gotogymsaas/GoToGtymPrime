# Facturación electrónica con Alegra

**Estado: el código está terminado y apagado.** Con la configuración actual la tienda no envía nada a Alegra: ni facturas oficiales ni borradores. Este documento explica lo que hay y, subrayado, lo que falta para ponerlo en marcha.

Alegra es el software de contabilidad y facturación de GoToGym. Es proveedor tecnológico autorizado por la DIAN: una factura emitida desde su API queda validada ante la DIAN y se envía al correo del cliente.

## Lo que ya está hecho

| Pieza | Dónde | Qué hace |
|---|---|---|
| Cliente de la API | [alegra_client.py](../gotogym/integrations/alegra/alegra_client.py) | Autenticación Basic, timeout de 15 s, errores sin credenciales ni URLs, búsqueda y creación de clientes y productos, creación y borrado de facturas |
| Emisión | [facturacion.py](../gotogym/orders/facturacion.py) | Arma el cliente y la factura desde el pedido, la emite y guarda el resultado. Idempotente y sin excepciones hacia afuera |
| Registro | modelo `Invoice` (`orders_invoice`) | Estado (`pending`, `processing`, `issued`, `failed`), número, CUFE, intentos, último error, respuesta de Alegra |
| Disparo | `confirm_payment` en [services.py](../gotogym/orders/services.py) | Al aprobarse el pago encola `emitir_factura`. Con la facturación apagada la tarea sale sin hacer nada |
| Reintentos | comando `emitir_facturas_pendientes` | Reemite las facturas pendientes o fallidas (hasta 5 intentos) |
| Vista previa | comando `previsualizar_factura` | Imprime lo que se enviaría para un pedido, sin red ni escritura |
| Documento del comprador | checkout y perfil | Tipo y número de documento, con la casilla «Usar datos de usuario» |

### De dónde sale cada dato de la factura

- **Cliente.** Nombre, correo y teléfono son los del pedido, que son los del checkout. Con la casilla «Usar datos de usuario» salen de la cuenta. El documento es el del pedido y, si el comprador no lo escribió, el de su cuenta (se edita en «Mi cuenta»).
- **Persona o empresa.** Con tipo NIT se crea como persona jurídica, con su dígito de verificación calculado. Con cualquier otro tipo, como persona natural.
- **Productos.** Cada SKU se busca en Alegra por su referencia y, si no existe, se crea. El envío va como una línea más (`ENVIO`).
- **IVA.** 19 %. Alegra espera el precio sin impuestos; con `ALEGRA_PRECIOS_INCLUYEN_IVA=true` el precio de la tienda se divide entre 1,19 antes de enviarlo.
- **Descuento de cupón.** Se reparte como el mismo porcentaje en todas las líneas de producto. El envío no se descuenta.
- **Moneda.** COP. Un pedido en otra moneda no se factura: queda fallido con un mensaje claro.
- **Medio de pago.** Mercado Pago. Se toma del pago aprobado: tarjeta de crédito, tarjeta débito, transferencia (PSE) o efectivo. Un tipo no reconocido, como dinero en cuenta, usa `ALEGRA_MEDIO_DE_PAGO`. La observación interna de la factura dice «Pagado con Mercado Pago (pago N)», y el número del pedido va como orden de compra.

### Qué no se factura

Pedidos sin pagar y pedidos cancelados, aunque su pago se aprobara (por ejemplo, por falta de stock): esos se reembolsan, no se facturan.

## Configuración actual

Las variables están en el `.env` local, que git ignora; los ids salen de una consulta de solo lectura a la cuenta de Alegra. En producción **no hay ninguna** declarada.

| Variable | Valor local | Para qué |
|---|---|---|
| `ALEGRA_EMAIL`, `ALEGRA_API_TOKEN` | la cuenta de soporte y su token | Credenciales (también sirven para la consulta en `/contabilidad/`) |
| `ALEGRA_FACTURACION_ACTIVA` | `false` | Interruptor general. Apagado, no se envía nada |
| `ALEGRA_EMITIR_ELECTRONICA` | `false` | Segundo seguro: aun encendida la integración, la factura no se emitiría ante la DIAN |
| `ALEGRA_IVA_PORCENTAJE` | `19` | Tarifa de IVA |
| `ALEGRA_PRECIOS_INCLUYEN_IVA` | `true` | Si el precio publicado ya trae IVA. <u>Es un supuesto: confirmarlo</u> |
| `ALEGRA_MEDIO_DE_PAGO` | `INSTRUMENT_NOT_DEFINED` | Medio de pago cuando Mercado Pago no lo informa |
| `ALEGRA_NUMBER_TEMPLATE_ID` | `18` | Numeración «Facturacion 2024» (prefijo GYM), la predeterminada para facturas de venta. <u>Confirmar que es la electrónica</u> |
| `ALEGRA_IVA_TAX_ID` | `3` | IVA 19 % de la cuenta. Vacío: las líneas van sin impuesto |
| `ALEGRA_CONSUMIDOR_FINAL_ID` | vacío | Contacto «Consumidor final», para compras sin documento. <u>No existe en la cuenta: hay que crearlo</u> |
| `ALEGRA_ITEM_GENERICO_ID` | vacío | Producto único para todas las líneas, en vez de uno por SKU |
| `ALEGRA_FACTURAR_DESDE` | vacío | Fecha desde la que se facturan pedidos pagados que no tienen factura |

## Probar sin enviar

```
python manage.py previsualizar_factura GTG-202610-0001
```

Imprime el cliente y la factura que se enviarían para ese pedido. No llama a Alegra, no escribe en la base y funciona con la facturación apagada. Los ids de Alegra aparecen como marcadores (`<id-cliente-alegra>`). Sirve para revisar importes, IVA, medio de pago y datos del cliente.

Las pruebas automáticas (`orders/test_facturacion.py`, `integrations/test_clients.py`) cubren todo el flujo contra un doble del cliente. Ninguna hace llamadas de red.

## Lo que falta para ponerlo en marcha

### En Alegra (trámites de la empresa)

1. <u>Habilitarse ante la DIAN como facturador electrónico</u>, con una <u>resolución de numeración electrónica</u> y una <u>firma digital activa</u>. Hasta entonces Alegra no puede emitir facturas oficiales. [Guía de Alegra](https://ayuda.alegra.com/col/implementar-facturacion-electronica-dian).
2. <u>Confirmar el plan de Alegra</u> que incluye la facturación electrónica por API. La documentación consultada no lo indica.
3. <u>Confirmar la numeración</u>. La cuenta (FRIENDS N GIFTS S.A.S., responsable de IVA, COP) ya tiene la numeración de facturas 18 como predeterminada y una «Nota Crédito Electrónica», lo que sugiere que ya factura electrónicamente. Falta verificar en Alegra que la 18 es la resolución electrónica vigente y no una de las otras «GYM» (ids 16, 17) o la inactiva «Principal» (id 1).
4. El IVA 19 % ya existe en la cuenta (id 3, cargado en `ALEGRA_IVA_TAX_ID`).
5. <u>Crear el contacto «Consumidor final»</u> y anotar su id para `ALEGRA_CONSUMIDOR_FINAL_ID`, si se van a aceptar compras sin documento. La búsqueda en la cuenta no encontró ninguno.
6. <u>Renovar el token de la API</u> antes de usarlo en producción: apareció en una captura de pantalla.

### En la configuración

7. <u>Declarar las variables en Azure</u> (`ALEGRA_EMAIL`, `ALEGRA_API_TOKEN` y las de arriba). Los scripts de `environments/azure/` ya listan las dos primeras; las nuevas están en `.env.release.example` con la facturación apagada.
8. <u>Confirmar si los precios publicados incluyen IVA</u> y ajustar `ALEGRA_PRECIOS_INCLUYEN_IVA`.
9. <u>Decidir qué pasa con una compra sin documento</u>: facturarla a «Consumidor final» o hacer el documento obligatorio en el checkout. Sin `ALEGRA_CONSUMIDOR_FINAL_ID`, esa factura queda fallida con el mensaje «El pedido no tiene documento del comprador».
10. <u>Programar `emitir_facturas_pendientes`</u> (WebJob de Azure, cada 15 minutos). Sin él, una factura que falla no se reintenta.
11. Decidir `ALEGRA_FACTURAR_DESDE`: <u>sin esa fecha el histórico de pedidos pagados no se factura</u>, que es lo seguro al activar.

### Pruebas antes de emitir en serio

12. <u>Probar contra el ambiente de pruebas de Alegra</u>, con `ALEGRA_EMITIR_ELECTRONICA=false` primero y con `true` después. La documentación de Alegra no deja claro el formato exacto de la respuesta (número y CUFE), ni si crear productos sin inventario es aceptado. Se guarda la respuesta completa en `raw_response` por si hay que ajustar la lectura.
13. <u>Comprobar que ciudades y departamentos del checkout coinciden con el catálogo de Alegra</u>. Un nombre distinto puede hacer rechazar la creación del cliente.
14. <u>Revisar con contabilidad el régimen del cliente</u>: hoy una empresa (NIT) se crea como responsable de IVA y una persona natural como no responsable.
15. <u>Revisar la factura de un pedido real con `previsualizar_factura`</u> y, ya en pruebas, con el PDF que genera Alegra. Con el descuento de cupón puede haber una diferencia de pesos frente al total cobrado.
16. Activar: `ALEGRA_FACTURACION_ACTIVA=true` y, cuando todo esté revisado, `ALEGRA_EMITIR_ELECTRONICA=true`.

## Pendiente de desarrollo (no bloquea el arranque)

- <u>Notas crédito</u> por reembolsos o devoluciones: hoy se tendrían que hacer a mano en Alegra. No se implementaron porque la documentación consultada no deja claro el esquema de Colombia.
- <u>Registrar el pago en la factura</u>: la factura queda abierta en Alegra y se concilia allí.
- <u>Pantalla de facturas fallidas</u> en el panel de administración: hoy se consulta la tabla `orders_invoice`.
- <u>Documento obligatorio</u> en el checkout, si se decide así.
- Tipo de documento PPT: Alegra no lo tiene y se envía como PEP.
- La emisión corre dentro del webhook de Mercado Pago y hace varias llamadas a Alegra. Si Alegra tarda, el webhook también (cada llamada tiene tope de 15 s). <u>Si se instala una cola de tareas</u>, `TASK_BACKEND` la usa sin tocar este código.
