# Estructura y arquitectura de GoToGymPrime

Estado verificado contra el código el 14 de octubre de 2026. Describe lo que existe hoy; las decisiones pasadas y los pendientes viven en otros documentos (ver el final).

## En una frase

Un monolito Django (`gotogym/`) que sirve la tienda, el blog, el panel administrativo y el panel de afiliados con plantillas HTML renderizadas en el servidor. No hay un frontend separado ni microservicios.

## Estructura del repositorio

| Ruta | Qué contiene |
|---|---|
| `gotogym/` | El proyecto Django: `manage.py`, la configuración (`gotogym/gotogym/`) y todas las apps |
| `gotogym/static/` | CSS, JavaScript e imágenes del sitio. Los derivados de imagen AVIF/WebP viven en `static/derivados/` |
| `gotogym/media/` | Imágenes de producto subidas desde el panel (parte versionada) |
| `environments/` | Scripts de validación (backend, frontend, Azure) e instalación de hooks de git |
| `.github/workflows/` | Pipeline de construcción y despliegue a Azure App Service |
| `.githooks/` | Validación local antes de cada commit y cada push |
| `docs/` | Documentación, los textos legales en PDF y los PDF de benchmarking del e-commerce |
| `design/` | Fuentes tipográficas de la marca |
| `pyproject.toml` | Configuración de ruff, mypy y coverage |

## Apps de Django

| App | Responsabilidad | Modelos principales |
|---|---|---|
| `accounts` | Usuarios (correo como identificador), registro, login, perfil, libreta de direcciones | `User`, `CustomerAddress`, `CustomerSegment` |
| `products` | Catálogo | `Product`, `ProductVariant` (talla, color, precio propio y precio con descuento), `ProductMedia`, `ProductCategory`, `Brand`, `ProductTag`, `ProductReview` |
| `inventory` | Stock por variante y su historial | `Inventory`, `InventoryAdjustment` |
| `tienda` | Listado y ficha de producto, derivados de imagen | (sin modelos propios) |
| `carrito` | Carrito en la sesión del usuario (visitantes incluidos) | (sin modelos: vive en `request.session`) |
| `orders` | Checkout, pedidos, cupones | `Order`, `OrderItem`, `Address`, `Coupon` |
| `payments` | Pagos: proveedor simulado y de Mercado Pago, webhook, reembolsos | `PaymentTransaction`, `Refund` |
| `shipping` | Cotización de envío (simulada) | `ShippingQuote` |
| `blog` | Journal: entradas con referencias | `Post`, `Category` |
| `afiliados` | Programa de afiliados: solicitud, comisiones, retiros, clics | `PerfilAfiliado`, `Commission`, `WithdrawalRequest`, `ReferralClick`, `ConfiguracionProgramaAfiliados` |
| `administracion` | Panel interno: dashboard de ventas, analítica, productos, pedidos, cupones, usuarios, afiliados | `PanelSettings` |
| `analitica` | Eventos de uso del sitio, sin datos personales y solo con consentimiento de cookies | `EventoAnalitica` |
| `contabilidad` | Consulta de clientes y facturas en Alegra (solo personal) | (sin modelos) |

`gotogym/integrations/` contiene los clientes de proveedores externos: `mercadopago` (pagos y reembolsos), `alegra` (contabilidad) y `hubspot` (esqueleto sin integración real).

## Mapa de rutas

Todas las rutas públicas llevan prefijo de idioma (`/es/`, `/en/`, `/pt/`); el español es el predeterminado.

| Ruta | Quién entra | Qué es |
|---|---|---|
| `/es/` | Todos | Portada con catálogo destacado y Journal |
| `/es/tienda/`, `/es/tienda/producto/<id>/` | Todos | Catálogo y ficha de producto |
| `/es/carrito/` | Todos | Carrito (se conserva al iniciar sesión) |
| `/es/blog/`, `/es/acerca-de/`, `/es/contacto/` | Todos | Journal, ciencia de materiales, contacto |
| `/es/politica-*`, `/es/terminos/` | Todos | Políticas: privacidad, tratamiento de datos, cookies, cambios, devoluciones, garantía, envíos, pagos y términos |
| `/es/accounts/acceso/`, `/es/accounts/register/` | Todos | Login y registro (aceptan `?next=`) |
| `/es/pedidos-tienda/checkout/` | Con sesión | Checkout |
| `/es/pedidos-tienda/mis-pedidos/`, `/es/accounts/editar-perfil/` | Con sesión | Cuenta del cliente |
| `/es/afiliados/dashboard/` | Con sesión | Panel de afiliados |
| `/es/admin-panel/` | Personal (`is_staff`) | Panel interno: ventas, analítica (`/analitica/`), productos, pedidos, cupones, usuarios, afiliados, catálogos |
| `/es/contabilidad/` | Personal | Clientes y facturas de Alegra |
| `/es/admin/` (o la ruta de `ADMIN_URL`) | Superusuario | Administración de Django; solo superusuarios, con límite de intentos de acceso |
| `/pagos/webhook/mercadopago/` | Mercado Pago | Webhook (sin prefijo de idioma, verifica firma) |
| `/healthz` | Monitoreo | Comprobación de salud |

## Flujo de una compra

1. **Navegar y armar el carrito** sin cuenta: el carrito vive en la sesión y guarda `{id de variante: cantidad}`. El precio y la disponibilidad se recalculan siempre en el servidor.
2. **Checkout** exige sesión. Si la persona no la tiene, va al login con `?next=` y vuelve al checkout con el carrito intacto.
3. **Pedido**: `orders.services.create_order_from_cart` crea el pedido, sus líneas (con precio congelado), la dirección y la cotización de envío en una transacción, y guarda el cupón usado. El servidor registra el evento `order_created` del embudo.
4. **Pago**: `payments` crea el intento con el proveedor activo (`PAYMENT_PROVIDER`: `mock` por defecto, `mercadopago` para el real).
5. **Confirmación**: al aprobarse el pago, `confirm_payment` descuenta el stock con bloqueo y confirma el pedido. Si ya no hay stock, el pedido queda cancelado con una nota para revisión y se avisa a la persona; el reembolso se hace a mano desde el panel (pedido → reembolsar). Cancelar un pedido devuelve el uso de su cupón.
   Los pedidos que siguen pendientes de pago pasadas 48 horas (`ORDER_PAYMENT_WINDOW_HOURS`) se cancelan solos y devuelven el cupón; un pago que llega después de cancelar queda marcado para reembolso manual. La persona recibe correos al confirmarse el pago, al enviarse el pedido y al cancelarse.
6. **Posventa**: cambio de estado, cancelación, devolución y reembolso desde el panel. Cancelar o devolver revierte la comisión del afiliado.

## Configuración

Hay tres módulos de configuración, todos heredan de `gotogym/settings.py`:

| Módulo | Para qué | Base de datos |
|---|---|---|
| `gotogym.settings` | Producción (variables de entorno) | PostgreSQL vía `DATABASE_URL`; SQLite si no hay variable |
| `gotogym.settings_local` | Desarrollo | SQLite `db_local.sqlite3`, `DEBUG` activo |
| `gotogym.settings_test` | Pruebas y CI | SQLite, hash de contraseñas rápido, estáticos sin manifiesto |

Variables de entorno que lee la configuración: `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `CSRF_TRUSTED_ORIGINS`, `SITIO_URL`, `ADMIN_URL`, `TRUSTED_PROXY_HOPS`, `RATE_LIMIT_ENABLED`, `SECURE_HSTS_SECONDS`, `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `PAYMENT_PROVIDER`, `PAYMENTS_MOCK_UI_ENABLED`, `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`, `ALEGRA_API_TOKEN`, `HUBSPOT_PRIVATE_TOKEN`, `EMAIL_HOST` (con `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL`) y `SENTRY_DSN` (con `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`), `REDIS_URL` y `ORDER_PAYMENT_WINDOW_HOURS`.

## Calidad y pruebas

- **Pruebas**: `python manage.py test` desde `gotogym/` ya usa la configuración correcta de estáticos. La suite completa, como la corre el CI, es `python manage.py test . administracion --settings=gotogym.settings_test`.
- **Lint y tipos**: `ruff` y `mypy` (configurados en `pyproject.toml`).
- **Gobernanza de diseño**: `environments/frontend/check_design_governance.sh` impide que aumenten los colores hexadecimales dentro de las plantillas.
- **Antes de subir**: los hooks de `.githooks/` ejecutan la misma validación del CI (se activan con `bash environments/install_git_hooks.sh`).
- **Cobertura**: `python -m coverage run --rcfile=../pyproject.toml manage.py test . administracion --settings=gotogym.settings_test` y luego `coverage report`.

## Comandos de mantenimiento

| Comando | Qué hace |
|---|---|
| `seed_initial_data` | Crea la marca y las categorías iniciales |
| `seed_catalog` | Siembra o actualiza el catálogo base |
| `seed_journal` | Carga las entradas del Journal (`--solo-faltantes` no pisa las existentes) |
| `audit_catalog` | Auditoría de solo lectura de catálogo, variantes e inventario |
| `security_checklist` | Revisa variables sensibles del entorno donde se ejecuta |
| `generar_derivados_imagen` | Regenera las imágenes AVIF/WebP y su manifiesto |
| `cancelar_pedidos_vencidos` | Cancela los pedidos sin pagar pasado el plazo y devuelve sus cupones (el checkout y el panel también lo ejecutan; conviene programarlo cada hora) |
| `probar_correo <destinatario>` | Envía un correo de prueba con el SMTP configurado |
| `revisar_claves_heredadas [--rotar]` | Detecta (y con `--rotar` corrige) cuentas que aceptan una contraseña que estuvo publicada en el código |
| `confirmar_comisiones`, `aplicar_bajas` | Avanzan lo que depende del tiempo en el programa de afiliados (también corren al abrir sus paneles) |

## Integraciones

| Proveedor | Estado |
|---|---|
| Mercado Pago | Construido (preferencias, webhook con firma, reembolsos) y apagado por defecto; nunca se probó con credenciales reales |
| Alegra | Funcional para consultar clientes y facturas desde el panel de contabilidad; requiere `ALEGRA_EMAIL` y `ALEGRA_API_TOKEN` |
| HubSpot | Solo un esqueleto sin llamadas reales |
| Sentry | Se activa al declarar `SENTRY_DSN` |
| Correo (SMTP) | Se activa al declarar `EMAIL_HOST`; sin él, los correos salen por consola. Lo usan la recuperación de contraseña, los avisos del pedido y los del programa de afiliados |
| Idiomas | Selector ES / EN en el menú, el panel móvil y el pie; las rutas llevan `/es/` o `/en/` y la elección se guarda en la cookie `django_language`. Todo el sitio de cara al cliente está traducido al inglés (portada, tienda, carrito, checkout, cuenta, afiliados, Journal, políticas, términos y correos del pedido). Las políticas y los términos en inglés son una traducción de cortesía; prevalece el español. El contenido de la base de datos se traduce con el filtro `traducir` (el `.po` hace de diccionario). El portugués existe en los catálogos pero no tiene selector ni las traducciones nuevas. El panel de administración y los correos internos siguen en español. Regresión: `gotogym/test_ingles_completo.py` |
| Cookies y medición | Banner de cookies propio (`static/js/cookies.js`); la medición del uso del sitio es opt-in y se registra en la cookie `gtg_cookies` |
| Caché compartida | `REDIS_URL` si existe; si no, una tabla en la base de datos (`django_cache`, la crea `migrate`). Sin base declarada, memoria local |

## Despliegue

Se despliega a Azure App Service con el flujo de `.github/workflows/main_gotogymweb.yml`, que valida, empaqueta y publica por Kudu. El Startup Command del App Service (configurado en el Portal) migra, recolecta estáticos y arranca gunicorn con 2 workers; `environments/azure/startup.sh` es la versión de referencia versionada, que además carga las entradas del Journal. Los datos reales del entorno, las variables, las tareas periódicas, los respaldos y la lista previa a abrir al público están en `docs/DESPLIEGUE.md`.

## Otros documentos

- `docs/GUIA_ACCESO.md`: cómo ejecutar el proyecto y entrar a cada panel.
- `docs/DESPLIEGUE.md`: producción, variables de entorno, tareas periódicas, respaldos y lista previa a abrir.
- `docs/Politicas y Textos Legales GoToGym.pdf`: compilación de los textos legales del sitio; se genera desde el código.
- `docs/Terminos y Condiciones del Programa de Afiliados GoToGym.pdf`: términos del programa de afiliados.
- `docs/ecomerce/PDFs/`: benchmarking y dirección de diseño del e-commerce.
