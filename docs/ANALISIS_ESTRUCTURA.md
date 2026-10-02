# Estructura y arquitectura de GoToGymPrime

Estado verificado contra el código el 2 de octubre de 2026. Describe lo que existe hoy; las decisiones pasadas y los pendientes viven en otros documentos (ver el final).

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
| `docs/` | Documentación y los PDF de benchmarking del e-commerce |
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
| `influencer` | Programa de afiliados: solicitud, comisiones, retiros, clics | `InfluencerProfile`, `Commission`, `WithdrawalRequest`, `ReferralClick`, `InfluencerProgramSettings` |
| `administracion` | Panel interno: dashboard de ventas, analítica, productos, pedidos, cupones, usuarios, afiliados | `PanelSettings` |
| `analitica` | Eventos de uso del sitio, sin datos personales | `EventoAnalitica` |
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
| `/es/accounts/acceso/`, `/es/accounts/register/` | Todos | Login y registro (aceptan `?next=`) |
| `/es/pedidos-tienda/checkout/` | Con sesión | Checkout |
| `/es/pedidos-tienda/mis-pedidos/`, `/es/accounts/editar-perfil/` | Con sesión | Cuenta del cliente |
| `/es/influencer/dashboard/` | Con sesión | Panel de afiliados |
| `/es/admin-panel/` | Personal (`is_staff`) | Panel interno: ventas, analítica (`/analitica/`), productos, pedidos, cupones, usuarios, afiliados, catálogos |
| `/es/contabilidad/` | Personal | Clientes y facturas de Alegra |
| `/es/admin/` | Superusuario | Administración de Django |
| `/pagos/webhook/mercadopago/` | Mercado Pago | Webhook (sin prefijo de idioma, verifica firma) |
| `/healthz` | Monitoreo | Comprobación de salud |

## Flujo de una compra

1. **Navegar y armar el carrito** sin cuenta: el carrito vive en la sesión y guarda `{id de variante: cantidad}`. El precio y la disponibilidad se recalculan siempre en el servidor.
2. **Checkout** exige sesión. Si la persona no la tiene, va al login con `?next=` y vuelve al checkout con el carrito intacto.
3. **Pedido**: `orders.services.create_order_from_cart` crea el pedido, sus líneas (con precio congelado), la dirección y la cotización de envío en una transacción, y guarda el cupón usado. El servidor registra el evento `order_created` del embudo.
4. **Pago**: `payments` crea el intento con el proveedor activo (`PAYMENT_PROVIDER`: `mock` por defecto, `mercadopago` para el real).
5. **Confirmación**: al aprobarse el pago, `confirm_payment` descuenta el stock con bloqueo y confirma el pedido. Si ya no hay stock, el pedido queda cancelado con una nota para revisión y se reembolsa.
6. **Posventa**: cambio de estado, cancelación, devolución y reembolso desde el panel. Cancelar o devolver revierte la comisión del afiliado.

## Configuración

Hay tres módulos de configuración, todos heredan de `gotogym/settings.py`:

| Módulo | Para qué | Base de datos |
|---|---|---|
| `gotogym.settings` | Producción (variables de entorno) | PostgreSQL vía `DATABASE_URL`; SQLite si no hay variable |
| `gotogym.settings_local` | Desarrollo | SQLite `db_local.sqlite3`, `DEBUG` activo |
| `gotogym.settings_test` | Pruebas y CI | SQLite, hash de contraseñas rápido, estáticos sin manifiesto |

Variables de entorno que lee la configuración: `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `PAYMENT_PROVIDER`, `PAYMENTS_MOCK_UI_ENABLED`, `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`, `ALEGRA_API_TOKEN`, `HUBSPOT_PRIVATE_TOKEN`, `EMAIL_HOST` (con `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL`) y `SENTRY_DSN` (con `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`).

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

## Integraciones

| Proveedor | Estado |
|---|---|
| Mercado Pago | Construido (preferencias, webhook con firma, reembolsos) y apagado por defecto; nunca se probó con credenciales reales |
| Alegra | Funcional para consultar clientes y facturas desde el panel de contabilidad; requiere `ALEGRA_EMAIL` y `ALEGRA_API_TOKEN` |
| HubSpot | Solo un esqueleto sin llamadas reales |
| Sentry | Se activa al declarar `SENTRY_DSN` |
| Correo (SMTP) | Se activa al declarar `EMAIL_HOST`; sin él, los correos salen por consola |

## Despliegue

Se despliega a Azure App Service con el flujo de `.github/workflows/main_gotogymweb.yml`, que valida, empaqueta y publica por Kudu. `environments/azure/startup.sh` migra, recolecta estáticos y arranca gunicorn. Los pasos y la bitácora del despliegue de marzo de 2026 están en `docs/DESPLIEGUE_LOCAL.md`.

## Otros documentos

- `docs/GUIA_ACCESO.md`: cómo ejecutar el proyecto y entrar a cada panel.
- `docs/CORRECCIONES.md`: registro histórico de las primeras correcciones (febrero de 2026).
- `docs/Informe_Comparativo_Original_vs_Actual.md`: comparación entre el proyecto original y la versión de comercio electrónico.
- `docs/verificacion_funcional.md`: lista de funcionalidades planteadas; varias aún no existen en el código.
