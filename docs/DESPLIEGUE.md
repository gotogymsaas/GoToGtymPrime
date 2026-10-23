# Despliegue y operación de GoToGym Prime

Verificado contra Azure y el código el 14 de octubre de 2026. Para ejecutar el proyecto en tu equipo, ver `docs/GUIA_ACCESO.md`. La bitácora de marzo de 2026 que había en este lugar (`DESPLIEGUE_LOCAL.md`) quedó en el historial de git.

## Producción hoy

| Qué | Valor |
|---|---|
| Aplicación | App Service Linux `gotogym-prime`, grupo `rg-gotogym-prime`, Python 3.12, Always On |
| Dirección pública | `https://shop.gotogym.store` (y `gotogym-prime.azurewebsites.net`) |
| Base de datos | PostgreSQL, por la variable `DATABASE_URL` |
| Respaldos | El servidor flexible `psql-gotogym-prod` (grupo `rg-gotogym-data`) conserva respaldos automáticos 7 días, sin redundancia geográfica |
| Despliegue | Producción directa mediante el workflow de GitHub Actions; no hay slot adicional |
| HTTPS | `httpsOnly=true` en App Service y redirección defensiva en Django |

## Cómo se despliega

1. Un push a `main` (o ejecutar el workflow a mano) lanza `.github/workflows/main_gotogymweb.yml`.
2. El job `build` valida: ruff, import-linter, mypy, `manage.py check`, pruebas con cobertura, gobernanza de diseño y smoke del frontend.
3. El job `deploy` empaqueta y publica por Kudu (`zipdeploy`) y comprueba que el sitio responda.
4. El **Startup Command** que ejecuta el App Service (configurado en el Portal, no en git) es:

   ```
   python gotogym/manage.py migrate --noinput && python gotogym/manage.py collectstatic --noinput && gunicorn --chdir gotogym gotogym.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120 --error-logfile '-'
   ```

   El `migrate` es el del proyecto: adapta una base antigua del programa "influencer" y crea la tabla de caché (`django_cache`) si la caché vive en la base. `wsgi.py` no migra.

   **Antes de desplegar migraciones que agregan restricciones** (`CheckConstraint`), ejecutar contra la base real `python gotogym/manage.py verificar_restricciones`. Solo lee: lista las filas existentes que las violarían. PostgreSQL valida los datos al crear la restricción y, si alguna fila no cumple, `migrate` falla y la aplicación no arranca con el Startup Command de arriba.
5. `environments/azure/startup.sh` es una versión de referencia del mismo arranque que además carga el Journal (`seed_journal --solo-faltantes`). Producción **no** la usa; si hace falta cargar entradas del Journal, ejecutar ese comando por SSH.
6. **Catálogo ampliado.** La migración `administracion.0006_catalogo_ampliacion` se ejecuta sola con el `migrate` del arranque y deja el catálogo como el del panel local: crea 11 prendas (con inventario 0), ordena el catálogo, oculta Pantalón verde y X5 Generation Mujer y pone en 0 el inventario de los 7 productos antiguos. **Eso último sobrescribe su stock real**; cada variante que cambia deja un asiento manual en el kardex con la cantidad anterior, de modo que los valores previos se pueden reconstruir. Si algo falla (o faltan fotos en `media/products`), el error se registra y el arranque continúa sin los cambios; el mismo trabajo se hace después con `python gotogym/manage.py seed_catalog_ampliacion` (con `--dry-run` primero). La migración solo actúa si crea algún producto, así que en una base que ya los tiene no toca nada. El ajuste `CATALOGO_AMPLIACION_EN_MIGRACION = False` la desactiva (lo usa `settings_test`).

## Variables de entorno

Las lee `gotogym/gotogym/settings.py`. Con `DEBUG` apagado y sin `DJANGO_SECRET_KEY` la aplicación no arranca.

| Variable | Para qué | Estado en producción |
|---|---|---|
| `DJANGO_SECRET_KEY`, `DEBUG`, `DATABASE_URL` | Núcleo | Declaradas |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Dominios permitidos | Declaradas (`shop.gotogym.store` y el de Azure) |
| `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` | HTTPS | Obligatorias y activas |
| `SECURE_HSTS_SECONDS` | HSTS. Arranca en 3600 en producción; subir por etapas a 604800 y luego 31536000 | Sin declarar (usa 3600) |
| `SITIO_URL` | Dirección pública para los enlaces de los correos. Por defecto `https://gotogym.store`, que no es donde vive la tienda | Debe ser `https://shop.gotogym.store`; confirmar que está declarada antes de probar los enlaces |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | Correo real. Sin `EMAIL_HOST` los correos salen por consola. Valores y recursos en [Correo](#correo) | Declaradas el 17 de octubre de 2026; `probar_correo` entregó a la bandeja de entrada |
| `PAYMENT_PROVIDER`, `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`, `PAYMENTS_MOCK_UI_ENABLED` | Pagos. Por defecto `mock` | Faltan |
| `ALEGRA_EMAIL`, `ALEGRA_API_TOKEN` | Contabilidad y facturación (`ALEGRA_TOKEN` también se acepta) | Faltan |
| `ALEGRA_FACTURACION_ACTIVA` | Emite la factura de cada pedido pagado. Por defecto `false`. Detalle en [Facturación electrónica](FACTURACION_ALEGRA.md) | Sin declarar |
| `ALEGRA_NUMBER_TEMPLATE_ID`, `ALEGRA_IVA_TAX_ID`, `ALEGRA_IVA_PORCENTAJE`, `ALEGRA_PRECIOS_INCLUYEN_IVA`, `ALEGRA_EMITIR_ELECTRONICA`, `ALEGRA_MEDIO_DE_PAGO`, `ALEGRA_CONSUMIDOR_FINAL_ID`, `ALEGRA_ITEM_GENERICO_ID`, `ALEGRA_FACTURAR_DESDE` | Parámetros de la factura | Sin declarar |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | Monitoreo de errores | Obligatorios en producción; errores también salen por consola |
| `REDIS_URL` | Caché compartida en Redis. Sin ella y con `DATABASE_URL`, la caché es una tabla de la base | Opcional |
| `ADMIN_URL` | Ruta del administrador de Django (por defecto `admin/`); conviene una no obvia, por ejemplo `gestion-xxxx/` | Sin declarar |
| `TRUSTED_PROXY_HOPS` | Proxies de confianza delante de la aplicación (1 en producción) para obtener la IP real del cliente | Sin declarar (usa 1) |
| `RATE_LIMIT_ENABLED` | Límite de intentos de acceso y de uso (por defecto activo) | Sin declarar |
| `ORDER_PAYMENT_WINDOW_HOURS` | Horas antes de cancelar un pedido sin pagar (48) | Sin declarar |
| `RECURSOS_AFILIADOS_ROOT` | Carpeta del material de marca de afiliados | Sin declarar |

Plantilla completa: `environments/azure/.env.release.example`.

## Correo

El correo sale por **Azure Communication Services (correo)** usando SMTP; el proyecto no necesita código propio para ello, solo las variables `EMAIL_*`. El procedimiento paso a paso con el que se configuró está en [CONFIGURACION_CORREO.md](CONFIGURACION_CORREO.md).

| Qué | Valor |
|---|---|
| Recurso de comunicación | `acs-gotogym-prod` (grupo `rg-gotogym-app`, suscripción `Azure subscription 1`) |
| Recurso de correo | `email-gotogym-prod`, con el dominio `gotogym.store` conectado y verificado (dominio, SPF, DKIM y DKIM2) |
| Remitente | `DoNotReply@gotogym.store` (la única dirección dada de alta). `DEFAULT_FROM_EMAIL` debe ser `GoToGym <DoNotReply@gotogym.store>`: Azure rechaza cualquier remitente que no esté dado de alta, incluido el `no-reply@` que trae el código por defecto |
| Servidor SMTP | `smtp.azurecomm.net`, puerto 587, `EMAIL_USE_TLS=true` |
| Usuario SMTP | `gotogym-tienda` (usuario personalizado en `acs-gotogym-prod` → Email → SMTP Usernames), ligado a la aplicación de Microsoft Entra `gotogym-smtp` |
| Contraseña SMTP | El valor del secreto de cliente de esa aplicación (Entra → Certificates & secrets). **Caduca**: anotar su fecha al crearlo y renovarlo antes; al vencer, el correo deja de salir sin aviso y el síntoma es un error de autenticación en el log |
| DNS del dominio | Registrado y administrado en GoDaddy. Los registros de Azure ya están; quien tenga la cuenta de GoDaddy debe editarlos |
| Cuotas de envío | El resumen del dominio muestra 30 y 100 (por minuto y por hora, según el rótulo cortado del portal). Alcanza para el volumen actual; el límite de recuperación de contraseña (5 solicitudes cada 10 minutos por IP) queda por debajo |
| Seguimiento de aperturas | Apagado |

**Comprobar que entrega.** Desde SSH en el App Service: `python gotogym/manage.py probar_correo <destinatario>`. Si el backend activo es el de consola, el comando lo avisa. Sale con el diseño de marca de los correos reales.

**Diseño de los correos.** Todos salen como HTML de marca (cabecera con el logo, tipografía y colores de la marca, botón, fotos de los productos del pedido) y con una versión de texto. El contenido se escribe una sola vez (`gotogym/correo.py`) y las plantillas viven en `gotogym/templates/correo/`; el correo de recuperación de contraseña usa `accounts/templates/accounts/password_reset_email.html`. Las fotos y el logo se piden a `SITIO_URL`: si una imagen no existe en el servidor, el correo sale igual con un hueco. Para revisar el diseño sin enviar nada real: `python manage.py previsualizar_correos` genera todos los correos con datos de muestra (los crea en una transacción que se revierte) y escribe HTML en `vista_previa_correos/`; con `--enviar tucorreo@dominio.com` los manda además a una bandeja real y con `--idioma en` los del pedido salen en inglés.

**Si falla la autenticación.** El nombre de usuario largo que usa Azure para este tipo de credencial es `<recurso>.<id-de-la-aplicación>.<id-del-directorio>`; se puede probar como `EMAIL_HOST_USER` si el nombre corto fallara.

### Qué correos envía la aplicación y cuándo

| Correo | Cuándo sale | Si el envío falla |
|---|---|---|
| Recuperación de contraseña | Al pedirla desde `/accounts/password_reset/` (cuentas existentes; una cuenta inexistente no revela nada) | Django lo deja en el log (`django.contrib.auth`) y la persona ve igual la pantalla de "revisa tu correo" |
| Pedido recibido | Al crear el pedido, antes de pagar: resumen, aviso de que está pendiente de pago y plazo de `ORDER_PAYMENT_WINDOW_HOURS` horas (48 por defecto) antes de la cancelación automática. Sale por cada intento de compra, aunque la persona abandone el pago | Se registra en el log (`orders.correos`); la creación del pedido no se deshace |
| Pedido confirmado | Cuando el pago queda **aprobado** | Se registra en el log (`orders.correos`); la compra y el webhook no se deshacen |
| Pedido enviado, pedido cancelado | Al cambiar el estado del pedido; el cancelado también sale al vencer el plazo sin pagar o si un pago aprobado no se pudo atender | Igual que el anterior |
| Programa de afiliados | Solicitud recibida, **aprobada** (bienvenida con su código y enlace, el descuento que recibe quien compra con el código, su comisión, el mínimo y el plazo de pago, y los primeros pasos; los valores salen de la configuración del programa y del cupón del afiliado), rechazada, bajas, terminación, cambio de tasa, validación extendida y avisos generales | Se registra en el log (`afiliados.correos`) |

Los enlaces de los correos de pedidos y afiliados se arman con `SITIO_URL`; el de recuperación recibe el mismo valor al cargar `accounts/urls.py`, así que cambiarlo exige reiniciar la aplicación. Los correos de pedidos salen en el idioma en que se hizo el pedido. Hoy el envío ocurre dentro de la petición (`TASK_BACKEND=sync`) con un tiempo máximo de 10 segundos por conexión (`EMAIL_TIMEOUT`).

### Limitaciones conocidas

- Los correos remiten a `support@gotogym.store` para dudas, no a responder el correo (el remitente es `DoNotReply`). Confirmar que esa dirección existe y que alguien la lee.
- Los clientes de correo bloquean las imágenes hasta que la persona las permite, y algunos (Outlook de escritorio) no muestran imágenes WebP o AVIF: el correo se entiende sin ellas y usa el archivo original de cada foto.
- La tipografía de marca (TT Norms) no se puede cargar en un correo; los correos usan Helvetica o Arial.
- El nombre visible del remitente es "DoNotReply", no "GoToGym": lo toma Azure de la dirección dada de alta (MailFrom addresses → Display Name), no de `DEFAULT_FROM_EMAIL`. Se cambia dando de alta otra dirección en el recurso de correo; `DEFAULT_FROM_EMAIL` debe apuntar siempre a una dirección ya dada de alta, o Azure rechaza los envíos y los correos se pierden con un error solo en el log.
- Los correos de pedido solo están traducidos al inglés (`gotogym/locale/en/LC_MESSAGES/django.po`); en portugués salen en español. Al agregar textos nuevos, editar el `.po` y recompilar el `.mo` con `polib` (no hay `msgfmt` en Windows), como indica el README.
- La cancelación automática de pedidos sin pagar (y su correo) solo se ejecuta cuando alguien abre el checkout. Hasta que `cancelar_pedidos_vencidos` se programe cada hora (ver Tareas periódicas), el aviso puede salir mucho después de las 48 horas en una tienda con poco tráfico.
- El dominio publica **dos registros SPF**; solo puede haber uno. Debe quedar el que incluye `spf.protection.outlook.com` y `spf.azurecomm.net`, y borrarse el que solo incluye `spf.protection.outlook.com`. Se corrige en GoDaddy.
- Con `PAYMENT_PROVIDER` sin declarar el pago es simulado y `PAYMENTS_MOCK_UI_ENABLED` está apagado: en producción no hay forma de aprobar un pago, así que la confirmación de pedido no se puede ejercitar hasta configurar Mercado Pago (o encender el panel de simulación de forma temporal, que `security_checklist` marca como hallazgo mientras esté activo).

## Registro de errores

Todo WARNING o superior (404, 403, 405, 429, fallos de CSRF, excepciones no controladas y los `logger.error/warning` de cada app) se escribe en `logs/errores.txt`, en la raíz del repositorio. Una línea por evento, con el traceback debajo cuando lo hay:

```
2026-10-19 21:45:34,016 | ERROR | 500 | ref=BE9EE7D6 | ip=127.0.0.1 | usuario=anonimo | GET /prueba/explota/ | django.request | Internal Server Error: /prueba/explota/
```

- El archivo rota a los 5 MB y conserva 5 copias (`errores.txt.1` … `.5`). No se versiona.
- `LOG_DIR` cambia el directorio. En Azure App Service usar una ruta persistente, p. ej. `LOG_DIR=/home/LogFiles/gotogym`; el disco de la aplicación se pierde al reiniciar. Si el directorio no se puede escribir, el sitio arranca igual y los errores quedan solo en la consola.
- Se guarda el id del usuario (no su correo) y la ruta sin la cadena de consulta, para no acumular datos personales ni tokens.
- Las páginas 500 muestran una **referencia** (`ref=`). Si un cliente la reporta, `grep BE9EE7D6 logs/errores.txt` lleva a la línea y al traceback.
- Cada código tiene su página (400, 403, 404, 405, 429, 500) en `gotogym/errores.py`. El 500 es autónomo (`templates/errores/500.html`, sin base de datos ni estáticos).

## Tareas periódicas

No hay un programador desplegado. Cada una se ejecuta también al abrir la pantalla que la necesita, pero conviene programarlas (WebJob de Azure o una tarea programada):

| Comando | Cada cuánto | Qué hace |
|---|---|---|
| `python manage.py cancelar_pedidos_vencidos` | Cada hora | Cancela pedidos sin pagar pasado el plazo, devuelve sus cupones y envía el correo de pedido cancelado. No toca pedidos con un pago pendiente en el proveedor (por ejemplo, efectivo) |
| `python manage.py emitir_facturas_pendientes` | Cada 15 minutos | Emite en Alegra las facturas pendientes y reintenta las fallidas (hasta 5 intentos). No hace nada si `ALEGRA_FACTURACION_ACTIVA` está apagada |
| `python manage.py confirmar_comisiones` | A diario | Confirma comisiones de afiliados cuyo periodo de validación terminó |
| `python manage.py aplicar_bajas` | A diario | Aplica las bajas de afiliados con preaviso vencido |

## Facturación electrónica con Alegra

Está terminada y apagada (`ALEGRA_FACTURACION_ACTIVA=false`). Qué hace, cómo probarla sin enviar y todo lo que falta para activarla está en [FACTURACION_ALEGRA.md](FACTURACION_ALEGRA.md).

## Respaldos, restauración y reversión

- **Base de datos.** Restauración a un punto en el tiempo de los últimos 7 días: crea un servidor nuevo, no pisa el actual (`az postgres flexible-server restore --resource-group rg-gotogym-data --name <servidor-nuevo> --source-server psql-gotogym-prod --restore-time <fecha-hora-UTC>`). Ensayada el 15 de octubre de 2026: el servidor restaurado quedó listo con todos los datos (44 tablas, pedidos, catálogo y Journal) y tarda unos 30 minutos; se borró al terminar. Valorar subir la retención de 7 días.
- **Código.** Para volver a una versión anterior, ejecutar el workflow sobre el commit anterior o revertir el commit en `main`. La reversión debe validarse con el health check y los logs de arranque.
- **Archivos subidos.** Las imágenes que se suban desde el panel quedan en `gotogym/media/` dentro de la aplicación desplegada; verificar que ese almacenamiento persista entre despliegues (pendiente de resolver).

## Antes de abrir al público

1. `SITIO_URL`, `SENTRY_DSN` y, para cobrar, `PAYMENT_PROVIDER=mercadopago` con sus credenciales y el webhook registrado.
2. `httpsOnly=true` en Azure, `SECURE_SSL_REDIRECT=true` y comprobar que todo el sitio funciona por HTTPS antes de subir HSTS.
3. `PAYMENTS_MOCK_UI_ENABLED` apagado.
4. `python manage.py security_checklist` en el App Service.
5. Revisar que no exista el administrador heredado con una contraseña publicada: `python manage.py revisar_claves_heredadas`.
6. Catálogo, precios y existencias reales (`python manage.py audit_catalog`).
