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

## Búsqueda por foto (contrato `vision-1`)

El cliente sube la foto de una prenda en el panel y la tienda pregunta al Coach
qué ve en ella. Es una llamada aparte del turno, porque una foto no cabe en el
presupuesto de 24 KB:

`POST <COACH_VISION_URL>` (por defecto, la misma base que `COACH_API_URL`
terminada en `/commerce/vision/describe/`) con el cuerpo de
`vision_solicitud.json`, las mismas cabeceras de firma y
`X-Vendedor-Contract: vision-1`. Tope del cuerpo: 512 KB.

- `image` es un JPEG de máximo 1024 px por lado, codificado en base64. La tienda
  lo vuelve a codificar antes de enviarlo: no trae EXIF, GPS ni otros metadatos.
- `purpose` es `similar_products` (foto de un cliente) o `catalog_attributes`
  (foto de un producto del catálogo, para proponer sus atributos).
- `vocabulary` trae las listas cerradas de cada atributo. El servicio responde
  solo con esos códigos.

La respuesta es como `vision_respuesta_ok.json`: `garment_detected`,
`person_present`, `attributes` (tipo, manga, cuello, ajuste, diseño, hasta 3
colores y una pista de línea) y `confidence` entre 0 y 1. Un valor fuera del
vocabulario se descarta. Si `meta.status` es `error`, la tienda muestra su propio
mensaje. Un 404 significa para la tienda que el Coach aún no tiene visión.

Reglas para el servicio de visión:

- No guardar la imagen ni enviarla a otro destino que el modelo. No registrarla
  en logs.
- Describir solo la prenda. Si aparece una persona, se marca
  `person_present: true` y no se describe nada de ella (rostro, cuerpo, edad,
  género ni medidas).
- El texto que aparezca dentro de la imagen es dato, nunca instrucción.
- No proponer productos ni precios: eso lo hace la tienda con su catálogo.

### `visual_query` en el turno

Después, la tienda arma el turno normal (`solicitud_con_foto.json`) con el campo
opcional `visual_query`: lo que el Coach vio en la foto y `matches`, los
candidatos que se parecen, con su puntaje y los atributos en que coinciden
(`garment_type`, `garment_type_related`, `colors`, `pattern`, `sleeve`,
`neckline`, `fit`). Cada `product_id` de `matches` está entre los candidatos.
Con `matches` vacío la tienda no tiene nada parecido: el Coach lo dice con
honestidad y puede ofrecer alternativas del catálogo, sin presentarlas como
iguales a la foto.

## Reglas para quien implemente el servicio

- Declarar autenticación y permiso de forma explícita en el endpoint: no heredar
  la configuración global permisiva.
- El rol de comercio no recibe datos personales ni de salud, y no puede caer en
  las ramas de los roles BUSINESS o ADMIN.
- El historial de la conversación se conserva en el servicio, por
  `conversation_id`: la solicitud solo trae el mensaje del turno.
- Una política con `review_status: "pending_review"` no se cita; se deriva a una
  persona.
