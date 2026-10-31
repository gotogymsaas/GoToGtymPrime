# Contrato tienda ↔ Coach (versión 1)

Estos ejemplos pasan por `vendedor.contrato.validar_solicitud` y
`validar_respuesta` en las pruebas. Son la referencia para el servicio que
reciba las solicitudes.

## Solicitud

`POST <COACH_API_URL>` con el cuerpo de `solicitud.json` (JSON, UTF-8) y estas cabeceras:

| Cabecera | Contenido |
|---|---|
| `X-Coach-Key-Id` | Identificador de la clave de servicio. |
| `X-Coach-Timestamp` | Segundos desde la época, entero. Debe estar dentro de ±60 s. |
| `X-Coach-Signature` | HMAC-SHA256 en hexadecimal de `timestamp + "." + cuerpo_crudo`, con el secreto de servicio. |
| `X-Vendedor-Contract` | Versión del contrato (`1`). |

La firma se calcula sobre los bytes exactos del cuerpo recibido. No se debe
volver a serializar el JSON antes de verificarla. `vendedor.firma.verificar`
es la implementación de referencia.

El cuerpo no contiene correo, teléfono, documento, dirección ni códigos de
afiliado. Los precios son texto decimal. Tope: 24 KB y 8 candidatos.

## Respuesta

El cuerpo de `respuesta_ok.json`. Si `meta.status` es `error`, la tienda muestra
su propio mensaje con la opción de reintentar y respeta `retry_after_seconds`.
Los campos desconocidos se ignoran.

Acciones permitidas en `ui_actions`: `add_to_cart` (con `variant_id`),
`open_product` (con `product_id`), `go_checkout`, `open_contact`. Cualquier otra
se descarta. La tienda genera las etiquetas de los botones; `label` es opcional
y se ignora.

## Reglas para quien implemente el servicio

- Declarar autenticación y permiso de forma explícita en el endpoint: no heredar
  la configuración global permisiva.
- El rol de comercio no recibe datos personales ni de salud, y no puede caer en
  las ramas de los roles BUSINESS o ADMIN.
- El historial de la conversación se conserva en el servicio, por
  `conversation_id`: la solicitud solo trae el mensaje del turno.
- Una política con `review_status: "pending_review"` no se cita; se deriva a una
  persona.
