# GoToGym SHOP — Análisis técnico-funcional integral y Roadmap de implementación del e-commerce (MVP)

**Fecha de análisis:** 16 de septiembre de 2026
**Repositorio inspeccionado:** `GoToGtymPrime.zip` (rama del zip entregado), inspección directa de código, migraciones, templates, settings y admin.
**Fuentes cruzadas:** código real del repositorio · `Manuscrito_Rediseno_Competitivo_GoToGym_SHOP.pdf` · `Manuscrito_Direccion_Diseno_GoToGym_SHOP.pdf` · `roadmap_ecommerce_gotogym_shop.md` (análisis previo) · decisiones de negocio dadas en esta conversación.
**Regla de verdad:** cuando el código y los PDFs difieren, este documento se basa en el código. Los PDFs se usan como fuente de UX/negocio/estrategia, convertidos a requisitos técnicos cuando corresponde.

---

# 1. Diagnóstico ejecutivo

El repositorio es un monolito Django funcional pero **comercialmente incompleto**. Confirmé línea por línea las afirmaciones de ambos manuscritos y encontré **cuatro problemas adicionales no documentados** que cambian el orden de prioridad del roadmap:

1. **La base de datos de producción real hoy es MySQL, no PostgreSQL.** `settings.py` sólo usa PostgreSQL si existe la variable `DATABASE_URL`; en su ausencia cae a MySQL (`mysql-connector`/driver mysql, host `servergotogym.mysql.database.azure.com`). Los archivos `environments/azure/.env.release.example` y `environments/backend/.env.test.example` configuran explícitamente `MYSQL_*`, no `DATABASE_URL`. Es decir: **el supuesto de negocio "la aplicación utiliza PostgreSQL" no está confirmado por la configuración operativa actual**; el código soporta ambos motores pero el entorno de referencia documentado en el repo apunta a MySQL. Esto es una decisión pendiente crítica (ver sección 5) que afecta el Sprint 2.
2. **Existen tres superficies de administración de catálogo distintas y no unificadas:** Django Admin (`products/admin.py`), el panel propio `GoToGymAdmin`/`administracion` (`/admin-panel/`), y un tercer CRUD completo en `products/views.py` + `products/urls.py` (`/products/...`) **sin ningún decorador de autenticación ni `staff_required`**. Esto es un hallazgo de seguridad real, no hipotético: cualquiera con la URL puede crear/editar/eliminar productos, categorías y marcas hoy.
3. **`carrito/views.py` no valida método HTTP en `add_to_cart`** (confirmado: es una función sin `@require_POST`, callable por GET) y **no tiene `apps.py`** propio (usa autodetección de Django, funciona pero es inconsistente con el resto de apps).
4. **El catálogo semilla real (migraciones `0004`–`0006`) contiene 7 productos con talla/color codificados como texto libre dentro de `description`/`name`** (ej. *"tallas S, M y L"*, *"talla única"*), y **`media/products/` contiene 7 imágenes adicionales que no aparecen en ninguna migración** (`Camiseta_RunFree_Reflect.png`, `Tank_Top_AirFlow.png`, `Short_FlexLite.png`, `Leggings_PowerStretch.png`, `Chorcito_2.png`, `Rompevientos_SpeedWind.png`, `Camiseta_DryFit_Pro_yLwZK1A.png`). Esto indica que **la base de datos real (Azure) probablemente tiene más productos creados manualmente vía el panel admin que los que existen en migraciones**, lo cual es determinante para la estrategia de migración de datos (sección 7): no podemos migrar "lo que vemos en migraciones" como si fuera el catálogo completo; hay que migrar contra la base de datos real.

El resto de hallazgos de ambos manuscritos quedan **confirmados exactamente** contra el código:

| Hallazgo del manuscrito | Confirmado en código |
|---|---|
| Filtro `rating` sin campo en modelo | `tienda/views.py` filtra `rating__gte` sobre `Product`, que no tiene ese campo; el `except Exception: pass` silencia el error |
| `reviews_count`, `old_price`, `long_description` no existen en `Product` | Confirmado; `producto_detail.html` los referencia con `|default:` |
| Carrito en € / pago en COP | No se encontró texto de € literal en `cart_detail.html` en esta revisión de código (el manuscrito lo reporta desde capturas), pero sí se confirma que el shipping (`5`) es un entero fijo sin unidad/moneda explícita y **no viaja a Mercado Pago** |
| Shipping no incluido en preferencia de Mercado Pago | Confirmado exactamente: `views_checkout.py` construye `preference_items` sólo con los productos del carrito; el `shipping` de `cart_detail` nunca se envía |
| `checkout` exige login | Confirmado: `@login_required(login_url='/accounts/acceso/')` |
| No existe `Order`/`OrderItem`/webhook/`PaymentTransaction` | Confirmado: no existen esos modelos en ningún `models.py` del repo |
| `Product` es plano (sin variantes/SKU/talla/color/media múltiple) | Confirmado: 8 campos, una sola `ImageField` |
| Influencers acoplado a Home autenticada y PDP | Confirmado en `logged_home.html` y `producto_detail.html` |
| `add_to_cart` muta estado sin exigir POST | Confirmado |
| PDP con "Comprar ahora" que no procesa el POST | Confirmado: el `<form method="post" action="">` de `producto_detail.html` postea a la misma URL de detalle, y `tienda/views.py::producto_detail` no tiene rama para `request.method == 'POST'` |

**Conclusión ejecutiva:** el proyecto no necesita reescritura. Necesita (a) cerrar riesgos de seguridad e integridad transaccional ya presentes, (b) introducir un dominio comercial real (variante, inventario, orden, pago, envío) que hoy no existe en absoluto, y (c) evolucionar la UX sin desmontar Django. La arquitectura objetivo es alcanzable de forma incremental por una sola persona en aproximadamente **19 sprints de 3 días (~57 días, ~11–12 semanas)**.

---

# 2. Arquitectura actual (lo que existe realmente)

## 2.1 Estructura del repositorio

```
GoToGtymPrime/                      (raíz del repo, manage.py, apps de "negocio")
├── manage.py                       (usa gotogym.settings por defecto)
├── db.sqlite3, db_local.sqlite3    (bases locales ya presentes)
├── accounts/                       (User custom, login/registro, JWT API)
├── blog/
├── carrito/                        (sin apps.py, sin tests)
├── configuracion_marca/
├── contabilidad/                   (integración Alegra, sin modelos)
├── crm/                            (integración HubSpot)
├── influencer/
├── metricas/
├── products/                       (Product/ProductCategory/Brand + CRUD propio sin auth)
├── tienda/                         (PLP/PDP, sin modelos propios)
├── media/products/                 (imágenes reales, más que las migradas)
├── static/
├── locale/                         (es/en/pt)
└── gotogym/                        (paquete de configuración Django)
    ├── settings.py, settings_local.py, settings_test.py
    ├── urls.py
    └── templates/ (home.html, logged_home.html, base.html, dashboard.html)

GoToGymAdmin/                       (proyecto secundario montado vía sys.path)
├── administracion/                 (panel /admin-panel/, staff_required, CRUD de Product)
└── gotogym_admin_project/

integrations/
├── mercadopago/mercadopago_client.py   (wrapper NO usado por carrito/views_checkout.py)
├── alegra/
└── hubspot/

environments/                       (scripts .env de ejemplo para azure/backend/frontend)
```

## 2.2 Apps Django activas (`INSTALLED_APPS`)

`admin, auth, contenttypes, sessions, messages, staticfiles, corsheaders, rest_framework, rest_framework_simplejwt, accounts, blog, products, configuracion_marca, contabilidad, influencer, tienda, carrito, crm, metricas, administracion`.

`administracion` vive físicamente en `GoToGymAdmin/` y se incorpora al `sys.path` desde `settings.py` (`ADMIN_PROJECT_DIR`). Es una integración funcional pero fràgil: dos repos lógicos comparten un mismo proceso Django vía manipulación de `sys.path`, sin ser un paquete instalado.

## 2.3 Modelo de datos actual

Sólo tres modelos de negocio de catálogo:

- `ProductCategory(name, description)`
- `Brand(name)`
- `Product(name, category FK, brand FK nullable, description, price DecimalField(12,4), discount PositiveInteger%, stock PositiveInteger, featured bool, image ImageField)`

`accounts.User` (custom, `AbstractUser` con `email` como `USERNAME_FIELD`, más `age`, `accepted_terms`, `show_influencer_modal`, `es_influencer`).

**No existen**: `ProductVariant`, `ProductMedia`, `Inventory`, `Order`, `OrderItem`, `Address`, `PaymentTransaction`, `Shipping`, `Review`, `Promotion`, `PersonalizationRequest`. Ninguno. El "modelo de datos objetivo" de los manuscritos es 100% nuevo, no una extensión menor.

## 2.4 Flujo de compra actual (real)

```
GET /tienda/  → producto_list (categoría preseleccionada, filtros incl. `rating` roto)
GET /tienda/producto/<pk>/ → producto_detail
   - form "Comprar ahora" → POST a la misma URL (no procesado, no-op funcional)
   - form "Añadir al carrito" → POST carrito:add_to_cart
GET|POST /carrito/add/<id>/ → session['cart'][id] += 1 (sin exigir POST)
GET /carrito/ → cart_detail (total = Σ price*qty + shipping fijo=5)
GET /carrito/checkout/ → @login_required
   → construye preference_items SOLO con productos (sin shipping)
   → mercadopago.SDK(...).preference().create(...)
   → redirect a init_point de Mercado Pago
   → back_urls success/failure/pending TODAS apuntan a cart_detail (no hay página de éxito real, no hay verificación de pago)
```

No hay: creación de orden, reconciliación con Mercado Pago, webhook, descuento de stock condicionado a pago, ni recibo.

## 2.5 Autenticación

`accounts.User` custom ya funciona con email como login (`USERNAME_FIELD='email'`), `LOGIN_URL='commercial_login'`, `LOGIN_REDIRECT_URL='logged_home'`. Es completamente reutilizable para "Store requiere login" sin crear nada paralelo — sólo hay que decorar las vistas de tienda/carrito con `@login_required`, que hoy sólo protege `checkout`.

## 2.6 Administración

- **Django Admin** (`/admin/`): registra `User`, `Product`, `ProductCategory` (no `Brand`).
- **Panel propio `administracion`** (`/admin-panel/`): `staff_required` (login + `is_staff`), CRUD de `Product`/`Category`/`Brand`, dashboard con conteos. Es el panel "de negocio" pensado para no-desarrolladores.
- **CRUD "products" app** (`/products/...`): mismo dominio, **sin ninguna protección de acceso**. Debe neutralizarse o protegerse en Sprint 0.

## 2.7 Configuración, entorno y seguridad

- `SECRET_KEY` con fallback inseguro `'change-me'` si no hay variable de entorno.
- `DEBUG` controlado por env var, default `False` (correcto).
- `ALLOWED_HOSTS` con default razonable para dominios conocidos.
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` todos apagados por defecto, activables por env var — **correcto en diseño, pero hay que verificar que estén activados en el entorno real de producción** (no verificable desde el zip, es un ítem de checklist de sprint de seguridad).
- `CORS_ALLOW_ALL_ORIGINS` apagado por defecto, con lista blanca — correcto.
- CSRF: middleware activo global; el problema no es CSRF en sí, es que `add_to_cart` no impone `POST`.
- Dependencias ya incluyen `psycopg2-binary` (Postgres) y `mercadopago>=2.1` — **no hace falta agregar dependencias nuevas para lo que pide este roadmap**, salvo ninguna (usamos lo ya instalado).

## 2.8 Internacionalización

`i18n_patterns` activo, `LANGUAGES=[es,en,pt]`, `locale/` presente. Las vistas de tienda/carrito no están dentro del bloque `i18n_patterns` en `urls.py`... **de hecho sí lo están**: `tienda` y `carrito` se incluyen dentro del mismo bloque `i18n_patterns(...)`. Esto es relevante porque todo lo que construyamos de Store seguirá bajo prefijo de idioma (`/es/tienda/...`), lo cual hay que respetar en el roadmap (usar `{% url %}` siempre, nunca URLs hardcodeadas).

---

# 3. Arquitectura objetivo

```
Experiencia (templates Django + JS progresivo, sin SPA)
  Home comercial · PLP (Store) · PDP · Carrito (server-rendered + fetch parcial) · Checkout · Cuenta/Pedidos · Recibo

Dominio comercial (apps nuevas o extendidas)
  catalog (extiende products): ProductVariant, ProductMedia
  inventory: Inventory (por variante) + movimientos con bloqueo transaccional
  orders: Order, OrderItem, Address
  payments: PaymentProvider (abstracción) + MockPaymentProvider + PaymentTransaction
  shipping: ShippingOption/ShippingQuote (MOCK) + snapshot en Order

Plataforma existente (se conserva)
  accounts (login/registro ya funcional) · administracion (panel admin evoluciona) ·
  Django Admin · i18n · Mercado Pago SDK (queda detrás de la abstracción) · Alegra/HubSpot (fuera de alcance del MVP)

Fuera del journey comercial (se desacopla, no se borra)
  influencer (se retira de Home/PDP/checkout; puede seguir vivo como sección propia)
```

Principio de diseño heredado de los manuscritos y aplicado como requisito técnico: **una sola fuente de verdad para el total** (carrito → checkout → `Order` → `PaymentTransaction` deben derivar del mismo cálculo de servidor; el precio y el stock nunca se confían desde el cliente).

No se migra a Next.js/SPA/microservicios en esta fase. Se documenta como evolución futura condicionada (sección 14).

---

# 4. Decisiones confirmadas (no reinterpretar)

1. Alcance MVP: catálogo, PLP, PDP, variantes, carrito, checkout, órdenes, inventario, pagos MOCK, envíos MOCK, estados de pedido, recibo interno, administración, políticas MOCK.
2. Fuera de alcance ahora: personalización/alta costura, reviews, wishlist, cupones, CRM avanzado, transportadoras reales.
3. **Login obligatorio** para Store/checkout, reutilizando `accounts.User` — se mantiene aunque los PDFs recomienden guest checkout (queda como recomendación futura, sección 14).
4. Base de datos: PostgreSQL como objetivo de entorno "real", SQLite para desarrollo local — **con la salvedad de la discrepancia MySQL/Postgres detectada en 2.7/5**, que debe resolverse antes del Sprint 2, no durante.
5. Catálogo inicial = productos reales existentes (migrados, no inventados). Marca = únicamente "GotoGym" a efectos de frontend (el modelo `Brand` puede conservarse a nivel de datos, pero no se expone como filtro/diferenciador de UX).
6. Variantes: talla + color como mínimo, con SKU, precio y stock por variante.
7. Regla de inventario: **el stock sólo se descuenta cuando el pago está aprobado**; nunca en add-to-cart, checkout u orden pendiente/rechazada/cancelada.
8. Orden persistente creada **antes** de iniciar el pago, con snapshot de producto/SKU/variante/precio/cantidad.
9. Pagos: **NO Mercado Pago real**. Abstracción `PaymentProvider` + `MockPaymentProvider` con estados pendiente/aprobado/rechazado/cancelado. Arquitectura preparada para `MercadoPagoPaymentProvider` futuro (preference_id, payment_id, external_reference, idempotencia, webhook) sin rehacer checkout.
10. Envíos MOCK con método, transportadora, costo, tiempo estimado, estado, tracking; el costo entra en el total único.
11. Checkout: datos de cliente + dirección, sin almacenar datos sensibles de tarjeta.
12. Estados de **pedido** y de **pago** son independientes (justificación técnica en sección 6.4).
13. Recibo interno (no factura fiscal).
14. Administración: extender el panel `administracion` existente, no crear un cuarto sistema.
15. Influencers: se desacopla del journey comercial, no se elimina el módulo.
16. UX: "product-first premium technology" aplicado sin comprometer la base transaccional; no se implementan aún personalización/gamificación/motion avanzado.

---

# 5. Decisiones pendientes (requieren definición de negocio, no resolubles solo con análisis técnico)

Sólo listo las que **realmente** no puedo resolver con ingeniería:

1. **Motor de base de datos real de producción hoy.** El código soporta MySQL (fallback) y PostgreSQL (vía `DATABASE_URL`), pero los `.env.example` del repo apuntan a MySQL Azure. Antes del Sprint 2 hace falta que el negocio/DevOps confirme: ¿la base de datos de producción hoy es MySQL o ya se migró a PostgreSQL con `DATABASE_URL`? Esto determina si el Sprint 2 es "consolidar Postgres" (motor ya correcto) o "migrar de MySQL a Postgres" (proyecto de migración de datos adicional, no cosmético). Este roadmap asume la segunda opción como peor caso y la trata explícitamente en el Sprint 2.
2. **Alcance de los "productos adicionales" en `media/products/`.** No puedo saber, sin acceso a la base de datos real de Azure, si esas 7 imágenes corresponden a productos ya creados manualmente vía el panel admin (y por tanto ya tienen fila en `Product`) o si son archivos huérfanos subidos y nunca asociados. Esto se resuelve en el Sprint 1 con un script de auditoría de datos (no requiere decisión de negocio, sólo acceso a la BD real antes de escribir el Sprint 3 en detalle).
3. **Textos legales/políticas MOCK**: el negocio debe validar el copy final antes de producción (no bloquea el MVP, ya que se definen como contenido provisional).
4. **Proveedor de envío real y transportadora** a futuro — no se resuelve en este documento por ser explícitamente fuera de alcance.

Todo lo demás (modelo de datos, transacciones de inventario, arquitectura de pagos, checkout, admin) es resoluble con ingeniería y queda decidido en este documento.

---

# 6. Modelo de datos objetivo

## 6.1 Principio de evolución

`Product` deja de ser la unidad vendible y pasa a ser la ficha comercial (nombre, historia, categoría). La unidad vendible es `ProductVariant`. Esto es el cambio estructural más importante del proyecto.

## 6.2 Modelos nuevos y su relación con lo existente

| Modelo | Estado | Campos esenciales | Relación / notas |
|---|---|---|---|
| `Product` | **Se conserva y se recorta** | `name, slug (nuevo), category FK, description, base_price (renombre de price), featured, status (nuevo: activo/borrador), image` (queda como imagen de portada/fallback) | `discount` y `stock` a nivel de producto quedan **deprecados** (no se leen desde Store nuevo; se conservan en BD por retrocompatibilidad de datos, no se eliminan en el MVP) |
| `ProductCategory` | Se conserva sin cambios | — | Ya sirve para PLP |
| `Brand` | Se conserva sin cambios, no se usa en filtros de UX | — | Sólo dato administrativo por ahora |
| `ProductVariant` | **Nuevo** | `product FK, sku (unique), size, color, price_override (nullable), is_active, created_at` | Precio efectivo = `price_override or product.base_price` |
| `ProductMedia` | **Nuevo** | `product FK, variant FK nullable, image, alt_text, sort_order, is_primary` | Permite reutilizar imágenes actuales de `Product.image` como primer `ProductMedia` de cada variante |
| `Inventory` | **Nuevo** | `variant OneToOne, quantity_available, quantity_reserved (no usado activamente en MVP, reservado para futuro), updated_at` | Descuento sólo en pago aprobado, con `select_for_update` |
| `Order` | **Nuevo** | `user FK, order_number (unique, humano), email, phone, currency='COP', subtotal, shipping_cost, discount_total, total, order_status, payment_status, created_at, updated_at` | Ver 6.4 sobre separación de estados |
| `OrderItem` | **Nuevo** | `order FK, variant FK (SET_NULL permitido para no romper si variante se borra), product_name_snapshot, sku_snapshot, size_snapshot, color_snapshot, unit_price_snapshot, quantity, line_total` | Snapshot íntegro: la orden nunca cambia aunque el catálogo cambie |
| `Address` | **Nuevo** | `order FK (o user FK reutilizable), full_name, phone, country, department, city, postal_code, address_line, address_complement, notes` | Para MVP basta relación 1–1 con `Order` (no se pide libreta de direcciones reutilizable todavía) |
| `PaymentTransaction` | **Nuevo** | `order FK, provider ('mock'/'mercadopago' futuro), preference_id, payment_id, external_reference, status, amount, currency, idempotency_key (unique), raw_payload (JSON), created_at, updated_at` | `external_reference = order.order_number` desde el día 1, aunque el proveedor sea mock |
| `ShippingQuote` | **Nuevo** | `order OneToOne, carrier_name (mock), method_name, cost, estimated_days, tracking_code (nullable), shipping_status` | Costo aquí es el mismo que entra en `Order.shipping_cost` (una sola fuente) |
| `Review` | No se crea | — | Fuera de alcance MVP |
| `Promotion` | No se crea | — | Fuera de alcance MVP |
| `PersonalizationRequest` | No se crea | — | Fuera de alcance MVP |

## 6.3 Por qué esta forma y no otra

- **`ProductVariant.sku` único** en vez de compuesto (`product_id+size+color`) porque el SKU es el identificador operativo real (inventario, recibo, futura integración con transportadora/facturación) y debe ser estable e independiente del PK.
- **`Inventory` como tabla separada de `ProductVariant`** (no un campo `stock` en la variante) porque así se puede aplicar `select_for_update()` sobre una tabla pequeña y de escritura frecuente sin bloquear lecturas de catálogo (que golpean `Product`/`ProductVariant`, de lectura frecuente).
- **Snapshots en `OrderItem`** (no FK "viva" a precio actual) porque es el único modo de garantizar que un cambio de precio o eliminación de variante no altere el histórico de una venta ya hecha — requisito explícito de negocio.
- **`Address` 1–1 con `Order`** y no un libro de direcciones de usuario: reduce alcance del MVP; es trivial de extender a "direcciones guardadas" después sin romper nada, porque el checkout ya pediría los mismos campos.
- **`PaymentTransaction` desde ya con `preference_id`/`payment_id`/`external_reference`/`idempotency_key`** aunque el proveedor sea mock: esto es lo que evita "reconstruir todo el checkout" cuando se integre Mercado Pago real (decisión de negocio §11, cumplida).

## 6.4 Estados: pedido vs pago (independientes, justificación técnica)

Deben ser independientes porque **no tienen la misma cardinalidad de transición ni el mismo dueño de la transición**:

- `payment_status` (`pending, approved, rejected, cancelled`) lo controla el proveedor de pago (hoy MOCK controlado por el desarrollador/pruebas; mañana webhook de Mercado Pago). Es un estado que **no debe ser editable manualmente por el admin** una vez que exista un proveedor real, para preservar integridad de conciliación.
- `order_status` (`pending_payment, confirmed, preparing, shipped, in_transit, delivered, cancelled`) lo controla la operación logística (hoy el administrador humano). Una orden puede estar `payment_status=approved` y `order_status=preparing` simultáneamente; son ejes distintos.
- Si se fusionaran en un solo campo, cualquier futuro webhook de pago pisaría estados operativos (ej. "enviado") o viceversa, y sería imposible representar "pago aprobado pero aún no se ha alistado el pedido".

Regla de transición dura (ver Sprint 4 y 9): `order_status` sólo puede avanzar a `confirmed` **si y sólo si** `payment_status == approved`. Esta regla vive en una función de servicio, no en el admin (para no depender de que el humano la respete).

## 6.5 Diagrama relacional (texto)

```
User 1───* Order 1───* OrderItem *───1 ProductVariant *───1 Product *───1 ProductCategory
                 │                                                 └──* ProductMedia
                 ├──1 Address
                 ├──1 ShippingQuote
                 └──1───* PaymentTransaction   (1 orden puede tener >1 intento de pago)

ProductVariant 1───1 Inventory
Product *───1 Brand (nullable)
```

---

# 7. Estrategia de migración de datos

## 7.1 Principios

- No se elimina ninguna tabla ni columna existente en el MVP. `Product.stock` y `Product.discount` quedan en BD pero dejan de ser la fuente de verdad para Store.
- La migración se hace en dos capas: **(a) migración de esquema** (Django migrations estándar, aditivas) y **(b) migración de datos** (script/`RunPython` idempotente, ejecutable en dev/staging antes de tocar producción).
- Todo el proceso debe ser **re-ejecutable sin duplicar datos** (usar `get_or_create` por `sku` igual que ya hace el propio repo en `0004_seed_gotogym_catalog.py` — es el patrón correcto y ya validado en este código).

## 7.2 Qué se conserva tal cual

- `ProductCategory` completo (nombre, descripción) — no se toca.
- `Brand` completo — no se toca, sólo deja de mostrarse como filtro.
- `Product.name`, `description`, `category`, `brand`, `featured`, `image` — se conservan como están.
- `Product.price` se conserva, pero se **renombra conceptualmente** a `base_price` (migración de esquema con `RenameField`, sin pérdida de datos).

## 7.3 Qué se transforma

- **Talla/color embebidos en texto libre** (`"tallas S, M y L"`, `"talla única"`, patrones detectados en las 7 filas semilla reales) se parsean con un script determinista:
  - Si el texto contiene "S, M y L" / "S, M, L" → generar 3 variantes de color único (el color mencionado en el nombre/descr., ej. "gris", "negro", "verde") × esas 3 tallas.
  - Si el texto contiene "talla única" → generar 1 variante `size='UNICA'` con el color detectado.
  - El color se extrae del `name` (patrón: primer color reconocido de una lista controlada: negro, gris, azul, verde, naranja, gris azulado…). Si no se detecta color con certeza, se usa `color='UNICO'` en vez de adivinar — **no se inventa un color que el texto no sugiere**.
- **Stock agregado de `Product.stock`** se reparte igualmente (o lo más igual posible) entre las variantes generadas del mismo producto, como stock MOCK inicial (ej. `stock=20` y 3 variantes → 7/7/6). Esto es una aproximación explícita, documentada como tal, no una medición real de inventario por talla (que hoy no existe en ningún sitio).

## 7.4 Qué se genera nuevo

- **SKU por variante**: patrón `GTG-{product_id:04d}-{size_code}-{color_code}`, ej. `GTG-0001-S-NEG`. Determinista y reproducible, evita colisiones, es legible para el equipo de operación.
- **`Inventory`** por cada `ProductVariant` nueva, `quantity_available` = el reparto del punto 7.3.
- **`ProductMedia`**: por cada `Product.image` existente, se crea 1 `ProductMedia(is_primary=True)` asociada al producto (no a una variante específica, salvo que en el futuro se suban fotos por color). Las variantes comparten esa imagen hasta que se suban fotos específicas por color vía el panel admin (Sprint 13).

## 7.5 Casos borde

- **Productos sin patrón de talla reconocible** (texto no matchea ninguna regla): se crea **una única variante `size='UNICA', color='UNICO'`** con todo el stock del producto. Nunca se bloquea la migración por un producto no parseable; se deja registrado en un log de migración (`INFO`/`WARNING`) para revisión manual posterior vía el panel admin, no se detiene el proceso.
- **Producto con `stock=0`**: se migra igual, con `Inventory.quantity_available=0` (no se oculta del catálogo salvo que se decida ocultar sin stock en Sprint 5, lo cual es una decisión de UX, no de migración).
- **"Productos huérfanos" detectados en `media/products/`** que no están en las migraciones semilla: antes de escribir el script definitivo de migración (Sprint 3), el Sprint 1 incluye una tarea de **auditoría de la base de datos real** (`manage.py shell` / management command de sólo lectura) contra el entorno real para confirmar cuántas filas de `Product` existen realmente hoy más allá de las 7 semilla. El script de migración de variantes se escribe para **todas** las filas de `Product` que existan en la BD real en el momento de ejecutarlo, no sólo para las 7 semilla.

## 7.6 Cómo evitar pérdida de datos

- Toda migración de datos se escribe como `migrations.RunPython(forward, reverse_noop)` — reversible a nivel de "no falla el `migrate` hacia atrás", aunque el `reverse` no reconstruya variantes borradas (se documenta explícitamente como migración de datos no simétrica, patrón estándar Django).
- Antes de ejecutar contra producción: **dump completo de la base de datos real** (`pg_dump`/`mysqldump` según corresponda tras resolver la decisión pendiente §5.1) como parte de los criterios de aceptación del Sprint 3.
- La migración se prueba primero contra una copia de la BD real importada en local/staging (no contra el `db.sqlite3` de desarrollo, que no tiene el catálogo real completo) — esto requiere el acceso mencionado en 7.5.

## 7.7 Cómo probar la migración antes de ejecutarla sobre datos importantes

1. Restaurar dump de producción en una base de staging aislada.
2. Ejecutar `migrate` (esquema) + comando de migración de datos en staging.
3. Verificar con un management command de auditoría: `Σ Inventory.quantity_available por producto == Product.stock original` (dentro de margen de redondeo), `count(ProductVariant) >= count(Product)`, `0 SKUs duplicados`, `0 ProductMedia huérfanas`.
4. Revisión manual en el panel admin (Sprint 13, o temporalmente vía Django Admin) de una muestra de productos migrados.
5. Sólo entonces se ejecuta contra producción, en ventana de mantenimiento, con el dump de respaldo confirmado.

---

# 8. Roadmap completo (sprints de ~3 días, 1 desarrollador full-stack)

Notación de complejidad: **B**=baja, **M**=media, **A**=alta.

## Sprint 0 — Auditoría de seguridad y datos reales (3 días · B/M)

**Objetivo:** cerrar los agujeros de seguridad ya existentes y confirmar el estado real de datos/infra antes de construir nada nuevo encima.

**Dependencias:** ninguna (primer sprint).

**Tareas backend:**
- Proteger `products/urls.py` completo: envolver todas las vistas de `products/views.py` con el mismo `staff_required` que usa `administracion/views.py` (login + `is_staff`), o si se confirma que ese CRUD es redundante con `administracion`, dejarlo devolviendo 404/redirect y documentarlo como deprecado (decisión técnica, no requiere negocio: es una app duplicada e insegura).
- Auditar `settings.py`: confirmar en el entorno real si `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` están en `True` en producción (variables de entorno del hosting, fuera del repo).
- Ejecutar contra la base de datos real (staging con dump, ver §7.7) un management command de solo-lectura que cuente: productos totales, categorías, marcas, usuarios, y liste imágenes en `media/products/` sin `Product` asociado.
- Confirmar decisión pendiente §5.1 (motor real de BD) con quien administre el hosting/Azure.

**Tareas frontend/templates:** ninguna visible al usuario final en este sprint.

**Base de datos:** ninguna migración de esquema todavía.

**Integraciones:** ninguna.

**Tests:** test de regresión que verifica que `/products/products/`, `/products/add-product/`, etc. devuelven 302/403 para usuario anónimo tras el fix.

**Criterios de aceptación:**
- Ningún endpoint de creación/edición/borrado de catálogo es accesible sin sesión `is_staff`.
- Documento corto (no código) con: motor de BD real confirmado, conteo real de productos/categorías, lista de imágenes huérfanas.

**Riesgos:** no tener acceso directo al entorno de Azure/hosting para confirmar env vars reales — mitigación: pedir el dump y las variables de entorno reales como bloqueante de este sprint, no asumir.

**Resultado:** el sistema actual deja de tener una puerta de administración de catálogo sin autenticación, y el equipo tiene certeza sobre los datos reales antes de diseñar la migración del Sprint 3.

---

## Sprint 1 — Estabilización transaccional del comercio actual (3 días · M)

**Objetivo:** el flujo de compra actual (sin variantes todavía) deja de tener inconsistencias de moneda/total/CSRF, y se retira influencers del journey comercial. Esto da una base estable sobre la cual construir el dominio nuevo sin arrastrar bugs conocidos.

**Dependencias:** Sprint 0.

**Tareas backend:**
- `carrito/views.py`: forzar `@require_POST` en `add_to_cart`, `update_cart`, `remove_from_cart` (con manejo explícito de `X-Requested-With` para JSON, tal como ya existe parcialmente).
- Eliminar el filtro `rating` de `tienda/views.py::producto_list` (campo inexistente) hasta que exista `Review` (fuera de alcance MVP).
- `tienda/views.py::producto_detail`: eliminar o inhabilitar el `<form>` "Comprar ahora" que postea a la misma URL sin handler (se retoma correctamente en Sprint 8, con semántica real de "seleccionar variante → checkout").
- Centralizar el cálculo de shipping/total en una función de servicio simple reusable (`carrito/services.py` o similar), aún con `Product`, como paso previo a que en Sprint 6 pase a usar `ProductVariant`.
- Crear `carrito/apps.py` (falta hoy) para alinear la app con el resto del proyecto.

**Tareas frontend/templates:**
- `logged_home.html`: retirar el bloque `quantum-hero__links--influencer`, el modal de warnings y el JS asociado.
- `home.html`: retirar el modal `influencer-modal` y `show_influencer_modal`.
- `producto_detail.html`: retirar el bloque final "¿Quieres convertirte en influencer...?" y el `<form>` "Comprar ahora" no funcional (se sustituye por un único CTA "Añadir al carrito" mientras no exista selección de variante).
- `cart_detail.html`: asegurar que el total mostrado usa exactamente el resultado de la función de servicio centralizada (una sola fuente de verdad, aunque todavía sin `Order`).

**Base de datos:** ninguna migración de esquema de catálogo. Puede requerir una migración trivial en `accounts` si se decide, más adelante, dejar de usar `show_influencer_modal` (no obligatorio en este sprint; basta con dejar de leerlo en templates).

**Integraciones:** ninguna todavía (Mercado Pago se toca en el Sprint 9 vía abstracción).

**Tests:**
- Unit: `add_to_cart` vía GET devuelve 405.
- Unit: cálculo de total del carrito (N productos, cantidades variables) coincide con suma esperada.
- Regresión: login, registro, blog, i18n siguen funcionando igual.

**Criterios de aceptación:**
- No hay ninguna mención a "influencer" visible en Home, Home autenticada, PDP.
- `add_to_cart` sólo responde a POST.
- El filtro roto de `rating` ya no existe en la vista.

**Riesgos:** que otras plantillas (no listadas explícitamente en esta auditoría) referencien las mismas clases CSS/JS de influencer y queden huérfanas — mitigación: `grep -r "influencer"` sobre todo `templates/` antes de dar el sprint por cerrado.

**Resultado:** el usuario final navega Store/PDP/carrito sin distracciones de influencer y sin poder romper el carrito con requests GET; el total del carrito es consistente.

---

## Sprint 2 — Infraestructura de base de datos (Postgres real + SQLite dev) (3 días · M/A, depende de §5.1)

**Objetivo:** dejar la configuración de settings y el pipeline de migraciones listos para trabajar de forma segura con PostgreSQL como motor "real" y SQLite en desarrollo, resolviendo la discrepancia MySQL/Postgres detectada.

**Dependencias:** Sprint 0 (decisión §5.1 confirmada).

**Tareas backend (rama A — si producción YA usa `DATABASE_URL`/Postgres):**
- Confirmar que `psycopg2-binary` (ya en `requirements.txt`) es la única dependencia necesaria — no agregar nada más.
- Eliminar/():marcar como deprecada la rama `mysql` de `settings.py` una vez confirmado que no se usa, o dejarla como fallback documentado explícitamente "sólo para compatibilidad histórica, no usar en nuevos entornos".
- Actualizar `environments/azure/.env.release.example` y `environments/backend/.env.test.example` para reflejar `DATABASE_URL` en vez de `MYSQL_*` (evita que alguien reintroduzca MySQL por copiar el ejemplo desconociendo el estado real).

**Tareas backend (rama B — si producción hoy usa MySQL real):**
- Todo lo de la rama A, más: **proyecto de migración de motor** antes de continuar con el resto del roadmap de e-commerce, porque construir `ProductVariant`/`Inventory`/`Order` con transacciones (`select_for_update`) sobre MySQL vs Postgres tiene semánticas de bloqueo distintas (InnoDB vs MVCC de Postgres) — se documenta la diferencia y se decide el motor **antes** de escribir el Sprint 4 (inventario transaccional), no después.
- Migración de datos MySQL → Postgres con herramienta estándar (`pgloader` o dump/restore con adaptación de tipos), en un sprint dedicado si aplica (este Sprint 2 puede necesitar extenderse a un Sprint 2-bis de 3 días adicionales sólo si la rama B se confirma; se marca como **riesgo de estimación** en la sección 16).

**Tareas comunes:**
- Verificar tipos de campo sensibles a motor: `DecimalField(12,4)` en `Product.price` (ambos motores lo soportan igual), `PositiveIntegerField` (igual), `ImageField`/rutas de `media` (independiente de motor).
- Confirmar `settings_local.py` (SQLite) sigue siendo el entorno de desarrollo día a día — no se toca.
- Revisar `settings_test.py`: ya usa SQLite + `MD5PasswordHasher` para tests rápidos — se mantiene, es correcto.

**Base de datos:** sin migraciones de esquema de negocio todavía; sólo cambios de configuración/motor.

**Tests:**
- `manage.py check --database default` limpio contra el motor definitivo.
- Suite completa existente (`accounts`, `blog`, `configuracion_marca`, `contabilidad`, `influencer`) corre en verde contra SQLite (dev) y contra el motor real elegido (staging).

**Criterios de aceptación:**
- Un solo motor de "verdad" para producción, documentado, sin ramas condicionales confusas en `settings.py` salvo el fallback explícitamente marcado como legado.
- `settings_local.py` sigue permitiendo desarrollo 100% offline con SQLite.

**Riesgos:** este es el sprint de mayor incertidumbre del roadmap completo, porque depende de una decisión de negocio/infra que no puedo confirmar desde el código (§5.1). Se trata explícitamente como riesgo #1 en la sección 17.

**Resultado:** base sólida y de motor único confirmado sobre la cual aplicar con confianza las migraciones transaccionales de inventario del Sprint 4.

---

## Sprint 3 — Modelo de catálogo: `ProductVariant` + `ProductMedia` + migración de datos reales (3 días · A)

**Objetivo:** el catálogo real queda representado con variantes y SKU, sin perder ni un producto existente.

**Dependencias:** Sprint 2 (motor de BD confirmado), auditoría de datos reales del Sprint 0.

**Tareas backend:**
- Nueva app `catalog_variants` (o extensión directa de `products`, recomendado: extender `products` para no fragmentar el dominio de catálogo en dos apps que ya conviven con `tienda`).
- Modelos: `ProductVariant`, `ProductMedia` (campos según §6.2).
- Migración de esquema (`makemigrations`) aditiva.
- Migración de datos (`RunPython`, patrón `get_or_create` por `sku`, igual que `0004_seed_gotogym_catalog.py`) implementando el algoritmo de parseo de §7.3–7.5, ejecutada primero contra staging (§7.7).
- Comando de auditoría post-migración (conteos, SKUs duplicados, huérfanos) reutilizando el script del Sprint 0.
- Renombrar `Product.price` → `Product.base_price` (migración `RenameField`, cero pérdida de datos).

**Tareas frontend/templates:** ninguna visible todavía (Store sigue leyendo `Product` en este sprint; el PLP/PDP nuevos llegan en Sprints 5–6). Sí se actualiza el panel `administracion` mínimamente para **listar** (sólo lectura) las variantes generadas, como forma de validar visualmente la migración.

**Base de datos:** migraciones de esquema + migración de datos (la más sensible de todo el roadmap).

**Integraciones:** ninguna.

**Tests:**
- Unit: función de parseo de talla/color contra los 7 casos reales conocidos (incluye "talla única" y "S, M y L").
- Integration: ejecutar la migración completa contra una copia de staging y verificar los 4 chequeos de §7.7 con un management command dedicado.
- Regresión: `producto_list`/`producto_detail` actuales (que siguen leyendo `Product`, no `ProductVariant`, en este sprint) no se rompen por el rename de `price`→`base_price` (actualizar sus referencias `producto.price` → `producto.base_price` como único cambio de compatibilidad).

**Criterios de aceptación:**
- 100% de los productos reales de la BD (no sólo los 7 semilla) tienen al menos 1 `ProductVariant` con SKU único.
- 100% de los `Product.image` existentes tienen su `ProductMedia` equivalente.
- Ningún producto queda sin representación (verificado por el comando de auditoría).

**Riesgos:** el algoritmo de parseo de texto libre es heurístico; puede generar variantes incorrectas para productos con redacciones no anticipadas. Mitigación: el comando de auditoría marca explícitamente (log) cada producto que cayó en el caso borde `size='UNICA', color='UNICO'` para revisión manual — no se asume éxito silencioso.

**Resultado:** el catálogo tiene una base de datos de variantes real, verificada y auditable, lista para que el resto del sistema (inventario, PLP, PDP, carrito, orden) la use como fuente de verdad.

---

## Sprint 4 — Inventario transaccional (3 días · A)

**Objetivo:** existe un modelo `Inventory` por variante y una función de servicio segura para reservar/descontar/reponer stock sin condiciones de carrera, aunque todavía no hay checkout de por medio (se prueba de forma aislada).

**Dependencias:** Sprint 3.

**Tareas backend:**
- Modelo `Inventory` (§6.2), migración de datos que reparte el stock heredado (§7.3) por cada `ProductVariant` recién creada.
- Módulo de servicio `inventory/services.py` con al menos:
  - `check_availability(variant, quantity) -> bool` (lectura simple, sin lock, para pintar UI de PLP/PDP).
  - `decrement_stock(order) -> None`, transaccional, usando `select_for_update()` sobre las filas de `Inventory` implicadas, ordenado por `variant_id` para evitar deadlocks entre transacciones concurrentes, y que **lanza una excepción específica** (`InsufficientStockError`) si en el momento de confirmar el pago ya no hay stock suficiente (caso de dos compradores casi simultáneos).
  - `restore_stock(order)` (para cancelaciones tras haber descontado, no usado en el flujo feliz pero necesario para el estado `cancelled` post-aprobación).
- Esta función **no se conecta todavía a Order/Payment** (eso es el Sprint 11); en este sprint se prueba de forma aislada con fixtures/tests directos sobre `Inventory`.

**Tareas frontend/templates:** ninguna (es un sprint 100% de dominio/backend).

**Base de datos:** nuevo modelo `Inventory` + migración de datos de reparto de stock.

**Tests (los más importantes de todo el roadmap, ejecutarse aquí primero de forma aislada y repetirse en Sprint 11 de forma integrada):**
- Unit: `decrement_stock` reduce exactamente la cantidad pedida.
- Unit: `decrement_stock` sobre stock insuficiente lanza `InsufficientStockError` y **no modifica** `quantity_available` (atomicidad — se prueba forzando rollback).
- Concurrencia: test con dos threads/transacciones simultáneas descontando la última unidad de la misma variante — sólo una debe tener éxito (usando `TransactionTestCase` de Django, no `TestCase`, porque `select_for_update` requiere transacciones reales, no la transacción envolvente de los tests estándar).

**Criterios de aceptación:**
- Ninguna operación de descuento de stock puede dejar `quantity_available` negativo, ni siquiera bajo concurrencia simulada en el test.
- El reparto de stock heredado desde `Product.stock` es auditable (suma por producto coincide con el original).

**Riesgos:** este es el segundo sprint de mayor riesgo técnico del roadmap (el primero es el Sprint 2). Si el motor real terminó siendo MySQL (rama B de Sprint 2), `select_for_update()` funciona pero con semántica de bloqueo de InnoDB; se debe re-ejecutar el test de concurrencia contra el motor real elegido, no sólo contra SQLite (SQLite no soporta bien bloqueos concurrentes reales — usar Postgres/MySQL de staging para este test específico, documentarlo así en el propio test).

**Resultado:** existe un mecanismo de inventario probado y seguro contra condiciones de carrera, listo para conectarse al flujo de pago en el Sprint 11.

---

## Sprint 5 — PLP / catálogo visual (3 días · M)

**Objetivo:** `tienda/views.py::producto_list` se convierte en un PLP real basado en `ProductVariant`/`Inventory`, con grid de cards, filtros funcionales (sin el bug de `rating`) y precio en COP.

**Dependencias:** Sprint 3, Sprint 4 (para pintar disponibilidad/estado de stock por variante, aunque sea agregado a nivel de producto en esta fase).

**Tareas backend:**
- Reescribir `producto_list` para anotar cada `Product` con: rango de precio (si varía por variante vía `price_override`), tallas/colores disponibles (distinct sobre `ProductVariant` con `Inventory.quantity_available > 0`), y badge de "agotado" si ninguna variante tiene stock.
- Filtros reales: categoría (ya existente, se conserva), talla, color, rango de precio, orden (nombre/precio asc-desc, ya existentes). Se elimina definitivamente cualquier referencia a `rating`.
- Paginación (no existe hoy) para evitar listar todo el catálogo sin límite.

**Tareas frontend/templates:**
- `producto_list.html`: grid responsive (2 columnas móvil, 3–4 desktop, según manuscrito de diseño), card con imagen (`ProductMedia` primaria), nombre, precio en COP formateado, chips de color/talla disponibles, badge "Agotado" cuando corresponda.
- Panel de filtros como `sidebar` en desktop y `drawer` en móvil (JS progresivo simple, sin framework nuevo).
- Quitar por completo el paradigma de selects de categoría/producto que oculta el listado (el hallazgo P0 más citado por ambos manuscritos).

**Base de datos:** ninguna migración nueva (usa lo creado en Sprint 3/4).

**Tests:**
- Unit: filtros por talla/color devuelven sólo productos con esa combinación disponible en `Inventory > 0`.
- Regresión: URL con parámetros de categoría sigue funcionando (compatibilidad con enlaces existentes/SEO, si los hay).

**Criterios de aceptación:**
- Un usuario anónimo o autenticado puede ver el catálogo completo en grid sin necesidad de elegir categoría/producto en un select previo.
- El precio mostrado está en COP, sin discrepancia con el precio que luego verá en PDP/carrito.

**Riesgos:** performance de anotaciones sobre `ProductVariant`/`Inventory` en listas grandes — mitigación: `select_related`/`prefetch_related` explícitos, medir con `django-debug-toolbar` si está disponible (no crítico para 7–50 productos actuales, sí documentarlo para escala futura).

**Resultado:** Store deja de ser "selector-first" y se convierte en un catálogo visual navegable, cumpliendo el principio P0 de ambos manuscritos.

---

## Sprint 6 — PDP premium sobre variantes reales (3 días · M/A)

**Objetivo:** `producto_detail` permite elegir talla/color reales (no simulados), muestra disponibilidad real por variante y el CTA queda con semántica correcta (sin el "Comprar ahora" roto).

**Dependencias:** Sprint 5.

**Tareas backend:**
- `producto_detail(request, pk)`: cargar `ProductVariant` + `Inventory` del producto; exponer estructura talla→color→(sku, disponible, precio efectivo) para que el frontend pueda pintar selectores dependientes sin llamadas adicionales.
- Endpoint ligero (JSON, mismo dominio, sin CORS nuevo) `GET /tienda/producto/<pk>/variante/` que, dado `size`+`color`, devuelve `sku`, `price`, `available` — usado por el selector de talla/color para actualizar precio/disponibilidad sin recargar página.
- Eliminar definitivamente el `<form>` "Comprar ahora" no funcional; el único CTA de esta fase es "Añadir al carrito", que ahora exige `variant_id` válido (no `product_id` suelto).

**Tareas frontend/templates:**
- `producto_detail.html`: galería (usa `ProductMedia`, aunque en el MVP la mayoría de productos sólo tendrán 1 imagen — el layout debe soportar de 1 a N sin romperse), selector de talla como botones (no dropdown, según ambos manuscritos), selector de color como swatches, precio y disponibilidad que se actualizan al cambiar variante, CTA "Añadir al carrito" deshabilitado si la combinación elegida no tiene stock.
- Retirar el bloque de 5 estrellas fake y `reviews_count`/`old_price`/`long_description` (campos inexistentes) — se deja un placeholder textual neutro ("Sin reseñas todavía") en vez de simular datos falsos, coherente con el principio "Evidencia antes que simulación" de los manuscritos.

**Base de datos:** ninguna nueva.

**Integraciones:** ninguna.

**Tests:**
- Unit: endpoint de variante devuelve 404 si la combinación talla/color no existe para ese producto.
- Unit: `available=False` cuando `Inventory.quantity_available == 0` para esa variante.
- E2E manual (documentado, no automatizado en este sprint): seleccionar variante, ver precio/disponibilidad actualizarse, agregar al carrito.

**Criterios de aceptación:**
- No es posible agregar al carrito sin haber seleccionado una combinación de talla/color válida y con stock.
- No aparece ningún dato simulado (estrellas, reviews, precio tachado) que no provenga de un modelo real.

**Riesgos:** productos migrados con variante única (`UNICA`/`UNICO`) deben seguir siendo comprables con un único botón "Añadir al carrito" sin selectores vacíos — validar explícitamente este caso en tests, no sólo el caso con múltiples variantes.

**Resultado:** la PDP es transaccionalmente correcta: lo que el usuario ve y selecciona es exactamente lo que existe en inventario real.

---

## Sprint 7 — Carrito basado en variantes, con login obligatorio (3 días · M)

**Objetivo:** el carrito de sesión pasa de `product_id` a `variant_id`, se valida disponibilidad en cada operación, y se exige login para todo el journey de Store (decisión de negocio §4.3), no sólo para checkout.

**Dependencias:** Sprint 6.

**Tareas backend:**
- `carrito/views.py`: `session['cart']` pasa a `{variant_id: quantity}`. `add_to_cart(request, variant_id)` valida `Inventory.quantity_available >= cantidad_solicitada_total_en_carrito` antes de aceptar (lectura, no lock — el lock real es en Sprint 4/11 al momento de pagar).
- Aplicar `@login_required` a `tienda:producto_list`, `tienda:producto_detail`, y a todas las vistas de `carrito` (no sólo a `checkout` como hoy) — cumpliendo la decisión de negocio de login obligatorio para todo Store.
- `cart_detail`: recalcular subtotal desde `ProductVariant.price_efectivo` (nunca desde un precio cacheado en sesión), usando la misma función de servicio centralizada creada en Sprint 1.
- Contexto processor `cart_count` actualizado para sumar cantidades por variante.

**Tareas frontend/templates:**
- `cart_detail.html`: mostrar imagen, nombre, talla, color, SKU, cantidad editable, subtotal por línea, y total — sin mención a shipping todavía (llega en Sprint 10, hoy se muestra "Envío: se calcula en el siguiente paso" para no repetir la inconsistencia actual).
- Redirección a login con `?next=` para cualquier intento anónimo de entrar a Store/carrito, reutilizando el mecanismo ya existente en `producto_detail.html` para influencers (mismo patrón, ya probado en el código).

**Base de datos:** ninguna migración nueva.

**Tests:**
- Unit: agregar más unidades de las disponibles en `Inventory` es rechazado con mensaje claro, sin modificar el carrito.
- Unit: el total del carrito no puede diferir del recalculado server-side aunque se manipule la sesión manualmente (se recalcula siempre desde variantes, nunca se confía un total guardado en sesión).
- Regresión: usuario anónimo que intenta `GET /tienda/` es redirigido a login con `next` correcto.

**Criterios de aceptación:**
- No existe ninguna ruta de Store/carrito accesible sin sesión autenticada.
- El carrito nunca permite una cantidad mayor a la disponible en inventario en el momento de la consulta.

**Riesgos:** usuarios que ya tenían un carrito en sesión con `product_id` (formato viejo) antes de este despliegue — mitigación: al leer `session['cart']`, si las claves no corresponden a `ProductVariant` válidos, se limpia el carrito automáticamente con un mensaje ("tu carrito se reinició por una actualización del sistema") en vez de fallar con 500.

**Resultado:** el carrito es seguro, coherente con inventario real, y el login obligatorio para Store queda implementado de forma consistente en todas las vistas, no sólo en checkout.

---

## Sprint 8 — Checkout: formulario + creación de `Order`/`Address` antes del pago (3 días · A)

**Objetivo:** existe un checkout real que crea una `Order` persistente con snapshot completo **antes** de tocar cualquier proveedor de pago.

**Dependencias:** Sprint 7.

**Tareas backend:**
- Modelos `Order`, `OrderItem`, `Address` (§6.2), migraciones.
- Vista `checkout_view` (reemplaza el `checkout` actual de `views_checkout.py`): `GET` muestra formulario (cliente + dirección), `POST` valida, y en una única transacción:
  1. Re-valida disponibilidad de cada `variant_id` del carrito contra `Inventory` (lectura, sin lock todavía — el lock definitivo es al aprobar pago, Sprint 11).
  2. Recalcula subtotal server-side desde `ProductVariant` (nunca confía precios de sesión/formulario).
  3. Crea `Order(order_status='pending_payment', payment_status='pending')` + `OrderItem` por cada línea con snapshot completo + `Address`.
  4. Vacía el carrito de sesión sólo si la orden se creó con éxito.
  5. Redirige a la pantalla de pago (Sprint 9), pasando `order.order_number`.
- Generador de `order_number` legible y único (ej. `GTG-{año}{mes}-{secuencial}`).
- Formulario de validación server-side de los campos de cliente/dirección de §13 del brief (nombre, apellido, email, teléfono, país, departamento, ciudad, código postal, dirección, complemento, info adicional) — validación real, no sólo `required` en HTML.

**Tareas frontend/templates:**
- Template de checkout de un solo paso (contacto + entrega en la misma pantalla, mostrando resumen del carrito al costado, según recomendación de "menor número de pasos posible" de los manuscritos, adaptado a que aquí sí hay login previo).
- Manejo de errores inline por campo (no un solo mensaje genérico).

**Base de datos:** migraciones de `Order`, `OrderItem`, `Address`.

**Integraciones:** ninguna todavía (el pago real llega en Sprint 9).

**Tests:**
- Unit: enviar checkout con stock insuficiente en alguna línea rechaza la creación de la orden con mensaje claro (no crea una `Order` a medias — todo dentro de una transacción atómica con `transaction.atomic()`).
- Unit: el total de `Order` es exactamente igual a la suma de `OrderItem.line_total` + `shipping_cost` (aunque `shipping_cost=0` en este sprint, antes del Sprint 10).
- Integration: `carrito → checkout → Order` end-to-end con datos válidos crea exactamente 1 `Order` y N `OrderItem` con snapshots correctos.

**Criterios de aceptación:**
- Toda `Order` creada tiene snapshot completo e independiente del catálogo vivo (verificable cambiando el precio de un `ProductVariant` después de crear una orden y confirmando que la orden vieja no cambia).
- No puede completarse un checkout con carrito vacío.

**Riesgos:** condiciones de carrera entre "checkout re-valida disponibilidad" y "otro usuario compra la última unidad" — se acepta en este sprint que la validación fuerte y con lock ocurre recién al aprobar el pago (Sprint 11); aquí sólo se hace una validación optimista para dar buen feedback de UX. Se documenta explícitamente para no generar falsa sensación de seguridad.

**Resultado:** existe una orden persistente, trazable, y verificable antes de que exista cualquier concepto de "pago" — cumpliendo el requisito de negocio §10 al pie de la letra.

---

## Sprint 9 — Abstracción `PaymentProvider` + `MockPaymentProvider` + `PaymentTransaction` (3 días · A)

**Objetivo:** existe una capa de pagos desacoplada del checkout, con un proveedor simulado que permite forzar cada estado (pendiente/aprobado/rechazado/cancelado), y arquitectura explícitamente preparada para Mercado Pago real sin tocar el checkout del Sprint 8.

**Dependencias:** Sprint 8.

**Tareas backend:**
- App `payments` nueva. Interfaz `PaymentProvider` (clase base o `Protocol` de Python) con métodos mínimos: `create_payment_intent(order) -> PaymentTransaction`, `get_status(payment_transaction) -> str`, `handle_callback(payload) -> PaymentTransaction` (este último no se usa activamente en MVP pero define ya la forma que tendrá el webhook real).
- `MockPaymentProvider(PaymentProvider)`: `create_payment_intent` crea un `PaymentTransaction(provider='mock', preference_id=<generado>, external_reference=order.order_number, status='pending', amount=order.total, currency='COP', idempotency_key=<uuid>)`. Expone una pantalla/endpoint de "simulación" donde (sólo en entornos no productivos, protegido por `settings.DEBUG` o un flag explícito `PAYMENTS_MOCK_UI_ENABLED`) se puede forzar el estado a `approved/rejected/cancelled` para probar todo el flujo manualmente.
- Vista `payment_pending_view(order_number)`: pantalla intermedia que muestra el total a pagar y, en modo mock, los botones de simulación.
- **No se implementa `MercadoPagoPaymentProvider` en este sprint** (queda para Sprint 18), pero la interfaz se diseña explícitamente pensando en sus campos reales (`preference_id`, `payment_id`, `external_reference`, `idempotency_key` ya existen en el modelo desde ahora).

**Tareas frontend/templates:**
- Pantalla de "pago pendiente" con resumen de orden y, en modo mock, controles de simulación claramente etiquetados como herramienta de pruebas (nunca visibles en producción real).

**Base de datos:** migración de `PaymentTransaction`.

**Integraciones:** el `integrations/mercadopago/mercadopago_client.py` existente **no se usa todavía**; se deja intacto para Sprint 18. `carrito/views_checkout.py` (el archivo viejo con la llamada directa al SDK) se **deprecia y se elimina** en este sprint, reemplazado por la nueva vista de checkout (Sprint 8) + `payments` (este sprint).

**Tests:**
- Unit: `create_payment_intent` genera exactamente 1 `PaymentTransaction` por intento, con `idempotency_key` único.
- Unit: forzar dos veces el mismo estado no duplica transacciones (idempotencia real, no sólo de nombre).
- Integration: `Order` recién creada → `create_payment_intent` → simular `approved` → `PaymentTransaction.status == 'approved'` (todavía sin tocar inventario, eso es Sprint 11).

**Criterios de aceptación:**
- Es posible simular los 4 estados de pago sin tocar código, sólo interactuando con la UI de pruebas.
- La interfaz `PaymentProvider` no tiene ninguna referencia a Mercado Pago en su firma (verificación de diseño: se podría implementar un proveedor Stripe con la misma interfaz sin tocar `payments`, `orders` ni `checkout`).

**Riesgos:** dejar la UI de simulación accesible por error en producción — mitigación: flag explícito + test que verifica que con `DEBUG=False` y el flag apagado la UI de simulación no se renderiza.

**Resultado:** existe un checkout completo y probable de punta a punta con pagos simulados, y la arquitectura ya está lista para enchufar Mercado Pago real sin rediseño (cumple el requisito de negocio §11 explícitamente).

---

## Sprint 10 — Shipping MOCK integrado al total único (3 días · M)

**Objetivo:** el costo de envío deja de ser un número fijo desconectado; se calcula (mock) durante el checkout y forma parte del mismo total que ve el usuario en carrito, `Order` y pago.

**Dependencias:** Sprint 8 (Order existe), puede hacerse en paralelo conceptual con Sprint 9 pero se numera después para mantener el checkout íntegro antes de tocarlo de nuevo.

**Tareas backend:**
- Modelo `ShippingQuote` (§6.2).
- Servicio `shipping/services.py::get_mock_quote(address, cart_weight_or_flat)` que devuelve un costo determinista simulado (ej. tarifa plana por ciudad principal vs "resto del país", **no** un número mágico hardcodeado en el template como hoy).
- Integrar en `checkout_view` (Sprint 8): al crear la `Order`, se calcula y persiste el `ShippingQuote`, y `Order.shipping_cost`/`Order.total` se recalculan incluyéndolo **antes** de pasar a `payments` (Sprint 9), de modo que `PaymentTransaction.amount` ya incluye envío desde el primer commit de este sprint en adelante.

**Tareas frontend/templates:**
- `cart_detail.html`: reemplazar "Envío: se calcula en el siguiente paso" (placeholder de Sprint 7) por una estimación visible ya en el carrito (mismo método mock, sin dirección todavía — se puede mostrar una tarifa base "desde $X" y el monto exacto en checkout una vez hay dirección).
- Checkout: mostrar desglose subtotal + envío + total antes de continuar a pago.

**Base de datos:** migración de `ShippingQuote`.

**Tests:**
- Unit: `Order.total == Order.subtotal + Order.shipping_cost - Order.discount_total` siempre (test de invariante, no sólo de un caso).
- Integration: el monto que ve `PaymentTransaction.amount` es idéntico al `Order.total` mostrado en checkout (el test crítico #5 pedido explícitamente en el brief: "total carrito = total checkout = total Order = total Payment").

**Criterios de aceptación:**
- No existe ningún punto del flujo donde el usuario vea un total distinto al que finalmente se factura vía `PaymentTransaction`.

**Riesgos:** bajo, es principalmente cableado de algo ya diseñado en sprints anteriores.

**Resultado:** cumplido el requisito de negocio §12 ("una única fuente de verdad para carrito/checkout/Order/Payment").

---

## Sprint 11 — Confirmación de pago → descuento real de inventario → recibo (3 días · A)

**Objetivo:** el evento "pago aprobado" (aún mock) dispara, de forma transaccional, el descuento real de stock (usando el servicio del Sprint 4) y genera el recibo interno. Es el sprint donde todas las piezas anteriores se conectan por primera vez de punta a punta.

**Dependencias:** Sprints 4, 9, 10.

**Tareas backend:**
- Función de servicio `orders/services.py::confirm_payment(order, payment_transaction)`, transaccional (`transaction.atomic()`), que:
  1. Verifica `payment_transaction.status == 'approved'`.
  2. Llama a `inventory.services.decrement_stock(order)` (Sprint 4) — si lanza `InsufficientStockError`, la orden pasa a un estado especial `payment_status='approved', order_status='cancelled'` con nota interna ("pago aprobado pero sin stock — requiere reembolso manual"), en vez de fallar en silencio. Este es el único caso borde real de "pago aprobado sin stock" y debe quedar explícitamente resuelto, no ignorado.
  3. Si el descuento es exitoso, `order.order_status = 'confirmed'`.
  4. Genera el objeto de recibo (puede ser un simple render HTML/PDF ligero a partir de los datos ya existentes en `Order`/`OrderItem`/`Address`/`PaymentTransaction`/`ShippingQuote` — no requiere modelo nuevo, el "recibo" es una vista, no una tabla).
- Enlazar esta función al flujo de simulación del Sprint 9: cuando se fuerza `approved` en la UI mock, se invoca `confirm_payment` automáticamente (así se prueba de punta a punta sin webhook real).
- Vista `order_confirmation_view(order_number)`: pantalla de éxito real (a diferencia de hoy, que redirige siempre a `cart_detail` sin verificar nada).

**Tareas frontend/templates:**
- Pantalla de confirmación con número de pedido, resumen completo, estado.
- Vista/plantilla de recibo imprimible (HTML simple, sin necesidad de librería de PDF en el MVP — puede añadirse `weasyprint`/similar en un sprint de hardening si se pide explícitamente factura descargable; en el MVP basta HTML).

**Base de datos:** ninguna nueva (usa lo ya creado).

**Tests (los "tests críticos" explícitamente pedidos en el brief, aquí es donde se implementan de forma integrada):**
- **Pago pendiente → stock intacto**: crear orden, no aprobar pago, verificar `Inventory.quantity_available` sin cambios.
- **Pago rechazado → stock intacto**: simular `rejected`, verificar `Inventory` sin cambios y `order_status` permanece `pending_payment` (nunca avanza a `confirmed`).
- **Pago aprobado → stock descontado exactamente**: verificar la resta exacta por cada `OrderItem`.
- **Stock insuficiente en el momento de aprobar → compra no se completa como exitosa silenciosa**: verificar que cae en el caso borde documentado arriba (orden marcada para revisión, no un 500 ni un descuento parcial).
- **Concurrencia real**: dos órdenes distintas compitiendo por la última unidad de la misma variante, ambas intentando `confirm_payment` casi simultáneamente — sólo una debe descontar con éxito (reutiliza el test de concurrencia del Sprint 4, ahora desde el flujo completo).

**Criterios de aceptación:**
- El flujo `Login → Store → Producto → Variante → Carrito → Checkout → Order → Pago MOCK aprobado → Confirmación → Inventario descontado → Recibo` se ejecuta sin inconsistencias, de forma reproducible.
- Todos los tests críticos de la sección 9 de este documento pasan.

**Riesgos:** este es el sprint de integración más delicado (junta 4 sprints anteriores); se recomienda no comprimirlo — si al día 3 no están todos los tests críticos en verde, extenderlo antes de avanzar al Sprint 12, ya que todo lo posterior depende de esta integración siendo correcta.

**Resultado:** **el MVP transaccional está, en esencia, terminado** desde el punto de vista del comprador. Lo que resta (Sprints 12+) es administración, seguridad, testing ampliado y UX.

---

## Sprint 12 — Estados de pedido + panel admin de órdenes/pagos (3 días · M)

**Objetivo:** el administrador puede ver y operar pedidos reales desde el panel `administracion` existente, sin crear un sistema paralelo.

**Dependencias:** Sprint 11.

**Tareas backend:**
- Extender `administracion/views.py` (mismo patrón `staff_required` ya usado) con: `orders_list` (filtrable por `order_status`/`payment_status`/fecha), `order_detail` (cliente, dirección, items, pago, envío), `order_update_status` (`POST`, sólo permite transiciones válidas de `order_status`, **nunca** permite al admin cambiar `payment_status` manualmente — ese campo es de solo lectura en el admin, coherente con la justificación de §6.4).
- Vista de listado de `PaymentTransaction` (solo lectura: proveedor, referencia, monto, estado) para trazabilidad/soporte.
- Vista de consulta de `Inventory` por variante (solo lectura en este sprint; edición manual de stock llega en Sprint 13 junto con el resto del CRUD de catálogo).

**Tareas frontend/templates:**
- Nuevas pantallas dentro del layout ya existente de `administracion` (reutilizar `dashboard.html`/estructura de `products.html` como base visual, no crear un design system nuevo para el admin).

**Base de datos:** ninguna nueva.

**Tests:**
- Unit: transición de `order_status` inválida (ej. `pending_payment → delivered` sin pasar por `confirmed`) es rechazada.
- Unit: intento de modificar `payment_status` desde el formulario de admin es ignorado/rechazado (protección server-side, no sólo ocultar el campo en el HTML).
- Permisos: usuario no-staff no puede acceder a ninguna de estas vistas.

**Criterios de aceptación:**
- El administrador puede seguir el ciclo de vida completo de un pedido real (creado en Sprint 11 vía mock) desde el panel, sin usar Django Admin ni la base de datos directamente.

**Riesgos:** bajo.

**Resultado:** operación real de pedidos posible sin intervención de desarrollador.

---

## Sprint 13 — Panel admin de catálogo: variantes, SKU, media, stock (3 días · M)

**Objetivo:** el panel `administracion` gana gestión completa de `ProductVariant`/`ProductMedia`/`Inventory`, cerrando el círculo de "administración" pedido en el brief (§16), y dejando de depender de migraciones para crear nuevas variantes.

**Dependencias:** Sprint 3, 4, 12.

**Tareas backend:**
- Extender `administracion/forms.py` con formularios de `ProductVariant` (crear/editar, con validación de SKU único) y `ProductMedia` (subida de imagen, marcar como primaria, orden).
- Vista de edición de `Inventory.quantity_available` por variante (edición manual directa, MOCK — no hay integración con almacén real).
- Retirar o marcar como legado el CRUD huérfano de `products/views.py` ya identificado en Sprint 0 (si en ese sprint sólo se protegió con auth, aquí se decide definitivamente: deprecar en favor de `administracion`, evitando mantener dos formularios de producto divergentes).

**Tareas frontend/templates:**
- `administracion/product_form.html` (o equivalente): sección de variantes inline (agregar/quitar talla-color-SKU-stock desde la misma pantalla de producto, patrón "formset" de Django).
- Galería simple de `ProductMedia` con reordenar/eliminar (reutilizando el patrón ya existente de `product_image_delete` en `administracion/views.py`).

**Base de datos:** ninguna nueva (usa modelos de Sprint 3/4).

**Tests:**
- Unit: no se puede crear una variante con SKU duplicado desde el formulario (validación server-side, no sólo constraint de BD dejando un 500).
- Unit: eliminar una `ProductVariant` referenciada por `OrderItem` existente está bloqueado o hace soft-delete (`is_active=False`), nunca borrado físico que rompería el snapshot histórico vía `SET_NULL` de forma silenciosa — se prefiere `is_active=False` y ocultarla del PLP/PDP en vez de borrar.

**Criterios de aceptación:**
- Se puede dar de alta un producto completo (ficha + variantes + imágenes + stock inicial) desde el panel admin sin tocar la base de datos ni ejecutar migraciones.

**Riesgos:** bajo/medio — la complejidad de formsets de Django es conocida pero requiere cuidado en el manejo de variantes existentes vs nuevas en el mismo submit.

**Resultado:** el catálogo es 100% gestionable operativamente, cerrando la dependencia de scripts de migración para el día a día.

---

## Sprint 14 — Cuenta del cliente, políticas MOCK y páginas de soporte (3 días · B/M)

**Objetivo:** el cliente autenticado puede ver su historial de pedidos, y existen las páginas de políticas requeridas (contenido provisional).

**Dependencias:** Sprint 11.

**Tareas backend:**
- Vista `my_orders_view` (dentro de `accounts` o una nueva vista ligera en `orders`) que lista `Order.objects.filter(user=request.user)` con acceso al detalle/recibo de cada una (reutilizando la vista de confirmación del Sprint 11 en modo "sólo lectura histórica").
- Vistas estáticas (o basadas en `flatpages`/templates simples) para: cambios, devoluciones, garantía, privacidad, tratamiento de datos, envíos, pagos, términos y condiciones — contenido MOCK, claramente reemplazable.

**Tareas frontend/templates:**
- Sección "Mis pedidos" enlazada desde el header/cuenta ya existente.
- Enlaces a políticas desde el footer/checkout (ej. "Al pagar aceptas nuestra Política de cambios" con enlace real, no un texto suelto).

**Base de datos:** ninguna nueva.

**Tests:**
- Unit: un usuario no puede ver pedidos de otro usuario (`Order.objects.filter(user=request.user)` probado explícitamente contra intento de acceso directo por `order_number` ajeno → 404, no 403 con fuga de existencia).

**Criterios de aceptación:**
- El cliente puede repasar su historial de compras y acceder a las políticas mínimas desde cualquier pantalla del checkout.

**Riesgos:** bajo.

**Resultado:** cierre del ciclo de "poscompra" mínimo pedido en el brief (§15/§17), sin construir todavía el dashboard completo de cuenta imaginado en los manuscritos (favoritos, direcciones guardadas, etc. — fuera de alcance, sección 14 de este documento).

---

## Sprint 15 — Seguridad y hardening específico del dominio comercial (3 días · A)

**Objetivo:** cerrar explícitamente cada ítem de la sección 30 del brief sobre el dominio nuevo (no repetir Sprint 0, que atacó lo ya existente; este sprint audita lo construido en Sprints 3–14).

**Dependencias:** Sprints 3–14 completos.

**Tareas backend:**
- Revisión explícita de que **ningún** precio, stock o total llega confiado desde el cliente en ninguna vista nueva (`carrito`, `checkout`, `payments`, `administracion` de órdenes) — auditoría línea por línea de cada `request.POST`/`request.GET` usado para cálculo.
- Revisión de permisos: cada vista de `administracion` nueva (Sprint 12/13) usa `staff_required`; cada vista de `orders`/`payments` de cliente usa `login_required` + filtro por `user` propio.
- Revisión de manipulación de IDs: acceso directo a `order_number`/`payment` de otro usuario devuelve 404 en todos los casos (no sólo en el de Sprint 14).
- Revisión de `idempotency_key` en `PaymentTransaction`: confirmar que reintentar la confirmación de un pago ya aprobado no vuelve a descontar stock (test explícito de doble-submit).
- Revisión de variables de entorno de producción: `DEBUG=False`, `SECRET_KEY` fuerte (no el default `'change-me'`), `ALLOWED_HOSTS` correcto, cookies seguras activas — checklist ejecutado contra el entorno real, no sólo contra el código.
- Rate-limiting básico (si no existe ya vía el hosting/proxy) sobre el endpoint de simulación de pago y sobre `add_to_cart`, para prevenir abuso trivial (no es un requisito bloqueante del MVP, pero sí de hardening antes de producción real — se marca explícitamente para la sección 13 de este documento).

**Tareas frontend/templates:** ninguna nueva; puede requerir ajustes menores de mensajes de error genéricos (nunca exponer detalle interno en 404/403).

**Base de datos:** ninguna.

**Tests:**
- Doble-submit de confirmación de pago no duplica descuento de stock.
- Acceso cruzado entre usuarios a pedidos ajenos siempre 404.
- Manipulación de `variant_id`/cantidad vía request directo (curl/Postman) nunca produce un total distinto al recalculado server-side.

**Criterios de aceptación:** checklist completo de la sección 11 de este documento en verde.

**Riesgos:** bajo si los sprints anteriores siguieron las reglas ya impuestas (recalcular siempre server-side); medio si se detecta algún atajo tomado bajo presión de tiempo en sprints previos — este sprint existe precisamente para detectarlo antes de producción.

**Resultado:** el dominio comercial nuevo queda auditado explícitamamente contra manipulación de precio/stock/identidad, no sólo "probablemente seguro por diseño".

---

## Sprint 16 — Testing integral y regresión completa (3 días · M/A)

**Objetivo:** consolidar la suite de tests dispersa en los sprints anteriores en una suite única, ejecutable con un comando, con cobertura explícita de los flujos críticos, y verificar que módulos no tocados (blog, i18n, influencer desacoplado, cuentas) siguen intactos.

**Dependencias:** Sprint 15.

**Tareas backend:**
- Consolidar tests unitarios de `inventory`, `orders`, `payments`, `shipping`, `carrito`, `tienda` bajo `tests/` por app (si no se hizo ya incrementalmente).
- Tests de integración explícitos para las cadenas: `carrito → checkout`, `checkout → Order`, `Order → Payment`, `Payment → Inventory` (los cuatro pedidos explícitamente en el brief, ya cubiertos parcialmente en Sprints 8–11, aquí se revisan como suite formal y se documentan).
- Suite de regresión: ejecutar los tests ya existentes de `accounts`, `blog`, `configuracion_marca`, `contabilidad`, `influencer` contra el estado final del código y confirmar que ninguno se rompió por los cambios de `settings.py` (Sprint 2), `Product` (Sprint 3) o `urls.py`/templates (Sprint 1).
- Verificar específicamente i18n: las nuevas plantillas de Store/checkout usan `{% trans %}`/`{% blocktrans %}` de forma consistente con el resto del proyecto (no se pide traducir todo el contenido nuevo a en/pt en el MVP, pero sí que la estructura no rompa `i18n_patterns`).

**Tareas frontend/templates:** ninguna nueva (este sprint es de verificación, no de construcción).

**Base de datos:** ninguna.

**Tests:** este sprint **es** la tarea; ver sección 10 de este documento para el detalle completo del plan.

**Criterios de aceptación:**
- `manage.py test` completo (todas las apps) en verde contra SQLite y contra el motor de producción elegido.
- Los 5 tests críticos explícitos del brief (§9 de este documento) están identificados por nombre en el reporte de tests y en verde.

**Riesgos:** encontrar en este sprint una regresión de un módulo no tocado (ej. `contabilidad`/Alegra) causada indirectamente por el cambio de `Product.price`→`base_price` si algún código de `contabilidad` lo referenciaba — mitigación: el `grep` de `Product.price` en todo el repo debió hacerse ya en el Sprint 3, pero este sprint es la red de seguridad final.

**Resultado:** confianza objetiva y medible (no "creo que funciona") de que el sistema completo es correcto y no rompió nada preexistente.

---

## Sprint 17 — UX, accesibilidad y rendimiento del flujo Store (3 días · M)

**Objetivo:** aplicar, sin tocar la base transaccional ya cerrada, las recomendaciones no negociables de accesibilidad/rendimiento de ambos manuscritos sobre las pantallas construidas en Sprints 5–11.

**Dependencias:** Sprint 16 (no se toca UX antes de que la base esté probada y estable).

**Tareas backend:** mínimas — puede requerir exponer `alt_text` de `ProductMedia` correctamente en el contexto de template si no se hizo ya.

**Tareas frontend/templates:**
- Foco visible y navegación por teclado en selectores de talla/color, filtros de PLP, y formulario de checkout.
- Contraste verificado (AA) en los estados de "agotado"/badges usados sobre negro grafito y sobre fondos claros, respetando la tabla de contraste ya calculada en el manuscrito de dirección de diseño (dorado/turquesa como acento, no como texto pequeño sobre blanco).
- `prefers-reduced-motion` respetado en cualquier transición ya introducida (hover de cards, cambio de variante).
- Imágenes de producto con `srcset`/tamaños explícitos para evitar CLS, `loading="lazy"` bajo el fold en PLP.
- Verificación manual de Core Web Vitals aproximados (Lighthouse local) en Home, PLP y PDP — no se exige tooling de monitoreo productivo en el MVP, sólo que las páginas no violen los umbrales de forma evidente.

**Base de datos:** ninguna.

**Tests:**
- Checklist manual de accesibilidad (teclado completo, lector de pantalla básico en PDP/checkout) — no se exige un test automatizado de accesibilidad en el MVP, se documenta como manual explícito.
- Lighthouse (o equivalente) ejecutado sobre PLP/PDP/checkout, resultados documentados (no hay servidor de producción real para medir p75 todavía; se toma como línea base local).

**Criterios de aceptación:**
- Checklist de la especificación no negociable del manuscrito de dirección de diseño (Anexo A) revisado ítem por ítem para las pantallas del MVP (no para personalización/alta costura, fuera de alcance).

**Riesgos:** bajo — es pulido, no reestructuración.

**Resultado:** la experiencia cumple los principios "product-first premium technology" sin haber comprometido la base transaccional, tal como pedía explícitamente el brief.

---

## Sprint 18 — Preparación de arquitectura para Mercado Pago real (sin activarlo) (3 días · M)

**Objetivo:** dejar todo lo necesario listo para que, en un proyecto futuro, activar Mercado Pago real sea "implementar una clase e invertir un flag", no "rediseñar checkout".

**Dependencias:** Sprint 9 (abstracción ya existe), Sprint 15 (seguridad ya auditada).

**Tareas backend:**
- Implementar `MercadoPagoPaymentProvider(PaymentProvider)` usando el `integrations/mercadopago/mercadopago_client.py` ya existente (que hoy no se usa desde ningún lado) — implementación completa de `create_payment_intent` (crea preferencia real con `external_reference=order.order_number`, incluyendo el `shipping_cost` en los items, corrigiendo el bug original documentado en la sección 1), pero **sin activarlo** por configuración (`PAYMENT_PROVIDER=mock` por defecto, cambiable a `mercadopago` sólo en un entorno de sandbox explícito, no en producción todavía).
- Endpoint de webhook `POST /payments/webhook/mercadopago/` que **existe y valida firma/origen**, pero cuya activación real de negocio queda pendiente de credenciales de producción reales (fuera de alcance de negocio actual, según §20). Se implementa contra el sandbox de Mercado Pago si hay credenciales de prueba disponibles; si no, se deja con tests unitarios contra payloads simulados documentados desde la documentación oficial de Mercado Pago.
- Idempotencia de webhook: cualquier notificación repetida con el mismo `payment_id` no vuelve a ejecutar `confirm_payment` dos veces (usa el mismo `idempotency_key`/verificación de estado ya diseñado desde el Sprint 9).

**Tareas frontend/templates:** ninguna visible (el checkout de cliente no cambia; sólo cambia qué proveedor procesa detrás).

**Base de datos:** ninguna nueva (los campos ya existían desde Sprint 9).

**Integraciones:** Mercado Pago SDK (ya en `requirements.txt`), esta vez detrás de la abstracción y con shipping incluido correctamente (corrigiendo el bug original).

**Tests:**
- Unit: `MercadoPagoPaymentProvider.create_payment_intent` construye una preferencia con `shipping_cost` incluido en los `items` o como cargo explícito (bug original corregido, con test de regresión que specifically covers this).
- Unit: webhook con payload duplicado no duplica `confirm_payment`.
- Integration (contra sandbox si hay credenciales, si no con mocks de `requests`): flujo completo simulando la respuesta de Mercado Pago sandbox.

**Criterios de aceptación:**
- El checkout del cliente (Sprints 8–11) no requiere ningún cambio de código para pasar de `mock` a `mercadopago`, sólo configuración.
- El bug histórico de shipping no incluido en la preferencia de pago queda corregido y cubierto por test, aunque el proveedor no esté activo en producción todavía.

**Riesgos:** depender de credenciales de sandbox reales de Mercado Pago que el negocio debe proveer — si no están disponibles a tiempo, el sprint entrega la implementación y los tests con mocks, dejando la validación end-to-end real como tarea de activación futura (no bloquea el cierre de este roadmap).

**Resultado:** cumplido el requisito de negocio §11 en su totalidad: arquitectura preparada, sin integración real activa, sin haber tenido que tocar el checkout ya probado en producción.

---

# 9. Dependencias entre sprints

```
Sprint 0 → Sprint 1 → Sprint 2 → Sprint 3 → Sprint 4
                                     │
                                     └────────────┐
Sprint 4 → Sprint 5 → Sprint 6 → Sprint 7 → Sprint 8 → Sprint 9 → Sprint 10 → Sprint 11
                                                                                   │
                              ┌────────────────────────────────────────────────────┤
                              ▼                                                    ▼
                        Sprint 12 → Sprint 13                              Sprint 14
                              │           │                                      │
                              └─────┬─────┴──────────────────────────────────────┘
                                    ▼
                              Sprint 15 → Sprint 16 → Sprint 17 → Sprint 18
```

Notas de secuencia:
- Sprint 12 (admin de órdenes) y Sprint 14 (cuenta/políticas) son **paralelizables entre sí en teoría**, pero como hay un solo desarrollador, se ejecutan en secuencia; se listan en ese orden porque el admin de órdenes es más crítico operativamente que la sección de cuenta del cliente.
- Sprint 13 depende de Sprint 3/4 (modelos) y de Sprint 12 (mismo layout de panel), no de Sprint 5–11.
- Sprint 17 (UX/accesibilidad) se puso deliberadamente **después** de Sprint 16 (testing), no antes, para no pulir visualmente algo que la suite de tests todavía podría obligar a cambiar estructuralmente.
- Sprint 18 (Mercado Pago real) puede ejecutarse en cualquier momento después de Sprint 9, pero se deja al final porque no es parte del alcance de negocio activo (§9/§20) y no debe distraer del cierre del MVP.

**Cambio respecto a la secuencia hipotética del brief:** el brief proponía Inventario (4) después de Catálogo/PLP (5)/PDP(6)/Carrito(7). Aquí se invirtió: **Inventario (Sprint 4) se hace inmediatamente después del modelo de variantes (Sprint 3) y antes de PLP/PDP/Carrito**, porque PLP y PDP ya necesitan leer disponibilidad real por variante para pintar "agotado"/habilitar CTA (Sprints 5 y 6 dependen explícitamente de Sprint 4). Construir PLP/PDP contra un inventario inexistente habría significado reescribirlas inmediatamente después.

---

# 10. Plan de testing

## 10.1 Unit tests
- Cálculo de totales (carrito, orden, envío) — invariante `total = subtotal + shipping - discount` en todos los escenarios.
- Parseo de talla/color en migración de datos (Sprint 3) contra los 7 casos reales conocidos + casos borde sintéticos.
- Servicio de inventario: descuento, reposición, rechazo por stock insuficiente (Sprint 4, ampliado en 11).
- Transiciones de estado de `order_status` (válidas/ inválidas) y protección de `payment_status` contra edición manual (Sprint 12).
- `PaymentProvider`/`MockPaymentProvider`: idempotencia, generación de referencia externa (Sprint 9).

## 10.2 Integration tests
- `carrito → checkout` (Sprint 8): stock insuficiente bloquea creación de orden; datos válidos crean orden con snapshot correcto.
- `checkout → Order` (Sprint 8): un `POST` de checkout produce exactamente 1 `Order` + N `OrderItem` + 1 `Address`.
- `Order → Payment` (Sprint 9): creación de `Order` habilita `create_payment_intent`; no es posible crear un intento de pago para una orden ya `confirmed`/`cancelled`.
- `Payment → Inventory` (Sprint 11): aprobación de pago descuenta stock exactamente una vez, con manejo explícito del caso de stock agotado entre el checkout y la aprobación.

## 10.3 Tests de regresión
- Login/registro/reset de password (`accounts`) sin cambios de comportamiento.
- Blog, `configuracion_marca`, `contabilidad`, `influencer` (desacoplado del journey pero funcional como módulo propio) siguen respondiendo igual.
- i18n: cambio de idioma (`/setlang/`) sigue funcionando sobre las nuevas rutas de Store/checkout.
- Panel Django Admin y panel `administracion` legado (antes de Sprint 12/13) no quedan rotos por el rename `price`→`base_price`.

## 10.4 Tests críticos (obligatorios, nombrados explícitamente)
1. **Pago pendiente → stock intacto.**
2. **Pago rechazado → stock intacto.**
3. **Pago aprobado → stock descontado exactamente.**
4. **Stock insuficiente → compra bloqueada** (tanto en checkout optimista como en confirmación con lock real).
5. **Total carrito = total checkout = total Order = total Payment**, verificado en un único test de integración de punta a punta.

Estos cinco tests se escriben por primera vez en los Sprints 8–11 y se re-ejecutan sin modificar su intención en el Sprint 16 como parte de la suite consolidada.

---

# 11. Seguridad

| Riesgo | Medida | Sprint |
|---|---|---|
| CRUD de catálogo sin autenticación (`products` app) | `staff_required` o deprecación | 0 |
| `add_to_cart` mutable por GET | `@require_POST` | 1 |
| Precio/stock confiados desde el cliente | Recalcular siempre server-side desde `ProductVariant`/`Inventory` | 6, 7, 8, 15 |
| Manipulación de `variant_id`/cantidad vía request directo | Validación server-side en cada capa (carrito, checkout, confirmación de pago) | 7, 8, 11, 15 |
| Acceso a pedidos/pagos de otro usuario | Filtrado por `user` + 404 explícito en vez de 403 | 14, 15 |
| Doble-submit de confirmación de pago | `idempotency_key` único + chequeo de estado antes de actuar | 9, 11, 15 |
| Edición manual indebida de `payment_status` por admin | Campo de solo lectura a nivel de formulario y de vista | 12 |
| `SECRET_KEY` default inseguro / `DEBUG` mal configurado en producción | Checklist de variables de entorno reales | 0, 15 |
| CSRF | Ya cubierto por middleware global; se refuerza exigiendo `POST` en todas las mutaciones nuevas | 1, 7, 8 |
| Webhook futuro de Mercado Pago sin verificar origen | Validación de firma/origen desde el diseño, aunque no esté activo | 18 |
| Datos sensibles de tarjeta | Nunca se solicitan ni almacenan (ni siquiera con proveedor mock) | 8, 9 |
| Cookies/HTTPS en producción | Confirmar `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE=True` en entorno real | 0, 15 |

---

# 12. MVP — criterio objetivo de finalización

El MVP se considera terminado cuando **todas** las siguientes condiciones son verificables (no opiniones, sino comprobaciones):

1. El flujo `Login → Store → Producto → Variante → Carrito → Checkout → Order → Pago MOCK → Confirmación → Inventario → Recibo` se ejecuta sin error para al menos un producto con múltiples variantes y uno con variante única.
2. Los 5 tests críticos de la sección 10.4 están en verde.
3. Ningún endpoint de catálogo, carrito, checkout, orden o pago es accesible sin la autenticación/autorización correspondiente (checklist de sección 11 en verde).
4. El administrador puede, sin tocar código ni base de datos directamente: dar de alta un producto con variantes, ver y actualizar el estado de una orden, y consultar transacciones de pago.
5. El catálogo real (todas las filas de `Product` existentes en la base de datos de producción al momento de migrar, no sólo las 7 semilla) fue migrado sin pérdida, auditado y verificado.
6. El total mostrado al usuario en cada paso (carrito, checkout, confirmación) es siempre idéntico al total procesado y persistido.
7. No queda ningún elemento del módulo de influencers visible en Home, Home autenticada, PLP, PDP, carrito, checkout o cuenta del cliente.
8. Existen políticas MOCK accesibles (cambios, devoluciones, privacidad, envíos, pagos, términos).

---

# 13. Hardening y producción (después del MVP)

Diferenciación explícita de niveles:

- **MVP funcional** = sección 12 completa (Sprints 0–14, más el núcleo de 15/16 que en la práctica se entrelaza).
- **Hardening** = Sprint 15 completo + revisión de configuración real de hosting (HTTPS forzado, cookies seguras, `SECRET_KEY` rotado, backups automáticos de base de datos, rate-limiting en endpoints sensibles, logging estructurado de errores de pago/inventario) + resolución definitiva de la discrepancia MySQL/Postgres (§5.1) si aún no se cerró en Sprint 2.
- **Producción** = hardening completo + monitoreo activo (errores, Web Vitals reales, tasa de aprobación de pagos) + plan de rollback documentado + ventana de despliegue con dump de respaldo confirmado + Sprint 18 sólo si el negocio decide activar Mercado Pago real (de lo contrario, producción puede lanzarse igualmente con pagos MOCK si esa es una decisión de negocio explícita, aunque no es lo recomendado para un e-commerce real con dinero de clientes).
- **Evolución futura** = todo lo listado en la sección 14 de este documento.

No se debe confundir "MVP funcional" con "listo para recibir pagos reales de clientes": el MVP usa pagos MOCK por decisión de negocio explícita (§11), por lo que **no debe exponerse públicamente como canal de venta real** hasta completar al menos el hardening y activar un proveedor de pago real (Sprint 18 + credenciales de producción).

---

# 14. Funcionalidades futuras (explícitamente fuera del MVP)

| Funcionalidad | Por qué queda fuera ahora | Cómo se incorporaría después |
|---|---|---|
| Personalización / Alta costura / `PersonalizationRequest` | Requiere workflow consultivo y preview, no forma parte del MVP transaccional | Nueva app `personalization`, reutilizando `ProductVariant`/`Order` como base; el modelo `PersonalizationRequest` de los manuscritos ya está diseñado conceptualmente en la sección 6 de ambos PDFs |
| Reviews verificadas | Requiere `verified_purchase` ligado a `OrderItem`, que recién existe desde Sprint 8 | Modelo `Review` con FK a `OrderItem` para verificar compra real, evitando el problema actual de reseñas simuladas |
| Wishlist | No afecta conversión del MVP | Modelo simple `Wishlist(user, variant)`, trivial una vez existe `ProductVariant` |
| Promociones / cupones | Añade complejidad de cálculo de totales antes de estabilizar la base | Modelo `Promotion` + hook en el servicio de cálculo de totales ya centralizado (Sprints 7/8/10) |
| CRM/HubSpot avanzado, automatizaciones de abandono de carrito | La integración `crm/hubspot_config.py` ya existe pero no está conectada al ciclo de compra nuevo | Conectar eventos de `Order`/`carrito` a HubSpot vía el cliente ya existente |
| Integración real de Mercado Pago | Decisión de negocio explícita de posponer | Sprint 18 ya deja la arquitectura lista; sólo falta activar credenciales de producción |
| Webhooks reales activos | Depende de lo anterior | Endpoint ya construido en Sprint 18, sólo pendiente de activación |
| Transportadoras reales / tracking real | Fuera de alcance de negocio actual | Reemplazar `shipping/services.py::get_mock_quote` por un cliente HTTP real, sin tocar `Order`/checkout |
| Guest checkout | Decisión de negocio actual es login obligatorio | Si se revierte la decisión, el checkout de Sprint 8 puede adaptarse a `user` nullable en `Order` sin rediseño estructural (el modelo ya contempla `user FK` no necesariamente obligatorio a nivel de BD, aunque hoy la vista lo exige vía `@login_required`) |
| Analítica avanzada, SEO programático, A/B testing | Explícitamente fuera de alcance por decisión de negocio | Instrumentación de eventos (`view_item`, `add_to_cart`, etc.) puede añadirse como capa no intrusiva sobre las vistas ya existentes |
| Migración a Next.js/SPA/microservicios | No hay razón técnica crítica detectada en esta auditoría que lo justifique hoy | Se evaluaría únicamente si personalización avanzada con preview en tiempo real, o necesidad de PWA offline, resultan imposibles de resolver razonablemente con templates Django + JS progresivo — no es el caso del MVP actual |

---

# 15. Matriz de trazabilidad

| Requisito | Fuente | Sprint | Componente | Estado |
|---|---|---|---|---|
| Retirar CRUD de catálogo sin auth | Código actual (hallazgo propio) | 0 | `products/urls.py`, `products/views.py` | Nuevo hallazgo |
| Confirmar motor real de BD | Código actual (hallazgo propio) | 0/2 | `settings.py`, `environments/*` | Decisión pendiente |
| `add_to_cart` sólo POST | PDF rediseño competitivo, roadmap previo | 1 | `carrito/views.py` | Confirmado en código |
| Retiro de influencers del journey | Ambos PDFs, roadmap previo | 1 | `home.html`, `logged_home.html`, `producto_detail.html` | Confirmado en código |
| Filtro `rating` inexistente | PDF rediseño competitivo, roadmap previo | 1 | `tienda/views.py` | Confirmado en código |
| PostgreSQL real / SQLite dev | Decisión de negocio | 2 | `settings.py`, `settings_local.py` | Decisión de negocio, riesgo técnico |
| `ProductVariant`/`ProductMedia` | Ambos PDFs (modelo de datos), decisión de negocio | 3 | `products/models.py` (o app nueva) | Nuevo |
| Migración de catálogo real sin pérdida | Decisión de negocio | 3 | migración de datos | Nuevo, crítico |
| `Inventory` transaccional | Decisión de negocio (regla de descuento en pago aprobado) | 4 | app `inventory` | Nuevo |
| PLP visual con filtros reales | Ambos PDFs (product-first, PLP) | 5 | `tienda/producto_list.html`/views | Rediseño |
| PDP con selector de talla/color real | Ambos PDFs (PDP premium) | 6 | `tienda/producto_detail.html`/views | Rediseño |
| Carrito por variante + login obligatorio Store | Decisión de negocio | 7 | `carrito/views.py` | Nuevo + decisión de negocio |
| `Order`/`OrderItem`/`Address` antes del pago | Ambos PDFs, decisión de negocio | 8 | app `orders` | Nuevo |
| `PaymentProvider` + Mock | Decisión de negocio | 9 | app `payments` | Nuevo |
| Shipping MOCK en total único | Ambos PDFs, decisión de negocio | 10 | app `shipping` | Nuevo |
| Descuento de stock sólo en pago aprobado | Decisión de negocio | 11 | `orders/services.py`, `inventory/services.py` | Nuevo, crítico |
| Recibo interno | Decisión de negocio | 11 | vista de confirmación | Nuevo |
| Admin de órdenes/pagos | Decisión de negocio | 12 | `administracion` (extensión) | Extensión |
| Admin de catálogo/variantes/stock | Decisión de negocio | 13 | `administracion` (extensión) | Extensión |
| Cuenta con historial de pedidos | Ambos PDFs (poscompra) | 14 | `accounts`/nueva vista | Nuevo |
| Políticas MOCK | Decisión de negocio | 14 | templates estáticos | Nuevo |
| Hardening de seguridad del dominio nuevo | Decisión de negocio (brief §30) | 15 | transversal | Auditoría |
| Suite de tests consolidada | Decisión de negocio (brief §29) | 16 | `tests/` por app | Consolidación |
| UX/accesibilidad/rendimiento | Ambos PDFs | 17 | templates/CSS Store | Rediseño |
| Arquitectura Mercado Pago real (sin activar) | Decisión de negocio | 18 | `integrations/mercadopago`, `payments` | Preparación |

---

# 16. Estimación total

| Rango | Valor |
|---|---|
| Número de sprints | 19 (Sprint 0 a Sprint 18) |
| Días estimados | 57 días hábiles (19 × 3) |
| Semanas estimadas (1 persona, jornada completa) | ≈ 11.4 semanas |
| Sprints de complejidad **alta** | 2 (BD/motor), 3 (migración de catálogo), 4 (inventario transaccional), 8 (checkout/Order), 9 (payment provider), 11 (integración de confirmación de pago), 16 (testing integral) — 7 de 19 |
| Incertidumbre de estimación más relevante | Sprint 2 (puede convertirse en 2 sprints si el motor real de producción es MySQL y hay que migrar datos entre motores, ver §5.1 y §8/Sprint 2) |

Estimación total ajustada considerando el riesgo del Sprint 2: **entre 57 y 60 días (11.4–12 semanas)**.

---

# 17. Riesgos principales (priorizados)

1. **Motor de base de datos de producción no confirmado (MySQL vs PostgreSQL vía `DATABASE_URL`).** Impacto: puede añadir un sprint completo de migración de motor antes de poder construir inventario transaccional con garantías. Mitigación: resolver en Sprint 0/2, antes de cualquier trabajo de dominio.
2. **Catálogo real en producción probablemente mayor que el catálogo semilla visible en migraciones** (evidenciado por imágenes huérfanas en `media/products/`). Impacto: el script de migración de variantes (Sprint 3) debe ejecutarse contra datos reales desconocidos hoy, no contra las 7 filas semilla. Mitigación: auditoría obligatoria en Sprint 0 antes de finalizar el diseño del script de Sprint 3.
3. **Condiciones de carrera en descuento de inventario bajo alta concurrencia real** (el MVP se prueba con tests de concurrencia simulada, pero el volumen real de tráfico puede exponer escenarios no cubiertos). Mitigación: `select_for_update` + tests de concurrencia explícitos en Sprints 4 y 11, y monitoreo temprano en producción real.
4. **Algoritmo heurístico de parseo de talla/color desde texto libre** puede generar variantes incorrectas para redacciones no anticipadas fuera de los 7 casos conocidos. Mitigación: caso borde explícito (`UNICA`/`UNICO`) + revisión manual señalada por el comando de auditoría, nunca fallo silencioso.
5. **Un solo desarrollador full-stack ejecutando 19 sprints de alta interdependencia**: cualquier retraso en Sprints 2–4 o 8–11 (la cadena crítica) se propaga linealmente a todo lo posterior. Mitigación: no comprimir esos sprints específicos aunque otros (ej. 14, 17) sí tengan margen.
6. **Dependencia de credenciales reales de Mercado Pago sandbox para validar Sprint 18 de punta a punta.** Impacto bajo (no bloquea el MVP), pero puede dejar esa preparación sin validación real hasta que el negocio provea credenciales.
7. **Doble/triple sistema de administración de catálogo coexistiendo hasta Sprint 13** (Django Admin, `administracion`, `products` app deprecada en Sprint 0). Mitigación: comunicar claramente al equipo/operación cuál es el panel "oficial" desde el Sprint 0, para evitar que alguien edite datos por Django Admin de forma inconsistente con las reglas de negocio nuevas (ej. crear un `Product` sin variantes vía Django Admin directamente).

---

# 18. Orden recomendado de ejecución (resumen para arrancar)

```
Sprint 0  — Auditoría de seguridad y datos reales
Sprint 1  — Estabilización transaccional actual + retiro de influencers
Sprint 2  — Infraestructura de base de datos (Postgres real + SQLite dev)
Sprint 3  — ProductVariant + ProductMedia + migración de catálogo real
Sprint 4  — Inventario transaccional
Sprint 5  — PLP / catálogo visual
Sprint 6  — PDP premium sobre variantes
Sprint 7  — Carrito por variante + login obligatorio en Store
Sprint 8  — Checkout + Order/Address antes del pago
Sprint 9  — PaymentProvider + MockPaymentProvider
Sprint 10 — Shipping MOCK + total único
Sprint 11 — Confirmación de pago → inventario → recibo
Sprint 12 — Admin de órdenes/pagos
Sprint 13 — Admin de catálogo/variantes/stock
Sprint 14 — Cuenta del cliente + políticas MOCK
Sprint 15 — Seguridad y hardening del dominio nuevo
Sprint 16 — Testing integral y regresión
Sprint 17 — UX / accesibilidad / rendimiento
Sprint 18 — Arquitectura Mercado Pago real (sin activar)
```

Este es el punto de partida para decir **"implementemos Sprint 1"** (o el Sprint 0, que es el que técnicamente debe ir primero) sin necesidad de repetir este análisis.
