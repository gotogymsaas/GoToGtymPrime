# Informe comparativo: GoToGym SHOP — estado original vs. versión actual

**Fecha:** 19 de septiembre de 2026
**Base de comparación:** commit `1f18d84` ("Use API-specific Azure deploy secrets", 2026-09-13), última confirmación en el historial de `main`. Todo lo descrito como "actual" es el árbol de trabajo de hoy — **nada de esto está confirmado (commiteado) todavía**; son cambios en curso sobre ese commit.
**Método:** cada afirmación de este informe está respaldada por `git diff HEAD`, `git status`, o la ejecución real de la suite de tests. No se describe nada de memoria sin haberlo verificado contra el árbol de trabajo actual.
**Alcance:** 73 archivos con cambios (38 modificados, 34 nuevos, 1 eliminado), 4 apps de Django completamente nuevas, 12 migraciones nuevas, y un cambio de fondo en cómo se procesa una compra de principio a fin.

---

## 1. Resumen ejecutivo

El repositorio original (`1f18d84`) tenía un catálogo de productos navegable y un botón de "comprar" que redirigía directo a Mercado Pago sin dejar ningún registro propio de la compra: no existía un modelo de pedido, no existía control de inventario, y el pago se resolvía por completo fuera del sistema. Es una arquitectura válida para un MVP de validación, pero no sostiene un negocio real: no hay forma de saber qué se vendió, no hay forma de reconciliar un pago con lo que el cliente pidió, y nada evita vender una prenda sin stock.

La versión actual reemplaza ese flujo por un dominio transaccional completo — variantes de producto (talla/color), inventario por variante con protección de condiciones de carrera, pedidos persistentes que se crean **antes** de redirigir a pagar, un proveedor de pago abstraído (simulado hoy, Mercado Pago real ya integrado y listo para activar con credenciales), cálculo de envío, y un panel de administración para gestionar todo lo anterior. Sobre esa base ya se hizo un primer trabajo de identidad visual: paletas de color reconciliadas contra el Brand Book real, componentización de plantillas, y una integración inicial (todavía parcial) de la identidad Quantum en el dominio comercial.

Nada de esto sale de la nada: cada capa se construyó siguiendo dos manuscritos de estrategia/diseño (`docs/ecomerce/PDFs/`) y dos roadmaps de implementación (`docs/ecomerce/Roadmap_Ecommerce_GoToGym_SHOP_v2.md` para el dominio transaccional, `Roadmap_Ecommerce_GoToGym_SHOP_Fase2.md` para lo visual/funcional posterior), y quedó verificado con 265 tests automatizados más verificación manual en vivo en cada paso.

**Lo más importante para quien lea esto antes de decidir sobre producción:** el sistema nunca se probó contra Mercado Pago real (solo contra un proveedor simulado), las traducciones a inglés/portugués no cubren ninguna de las 66 cadenas nuevas del dominio comercial, y el límite de tasa (`rate_limit`) usa una caché por proceso que no funciona correctamente con los 3 workers de Gunicorn que ya usa este proyecto. Los tres puntos se detallan en la sección 8.

---

## 2. Backend

### 2.1. Arquitectura de apps: qué existía, qué es nuevo

| App | Estado en `1f18d84` | Estado actual |
|---|---|---|
| `products` | Existía. `Product` con `price` plano, sin variantes ni medios múltiples. 6 migraciones. | Extendida: `Product.price` → `base_price`; se agregaron `ProductVariant` y `ProductMedia`. 9 migraciones (+3). |
| `tienda` | Existía, pero como capa de presentación pura: `models.py` vacío desde siempre, usa `products.models.Product` directamente. Vista de catálogo con selectores, sin variantes. | PLP con grid/filtros/paginación; PDP con selector de talla/color como botones, galería con carrusel. Nuevo módulo `catalog.py` (construcción de tarjetas de producto, matriz de variantes). |
| `carrito` | **No era una app de Django real**: no tenía `__init__.py`, `apps.py` ni `models.py` — solo `views.py`, `urls.py`, `context_processors.py` y una plantilla. El carrito guardaba `{producto_id: cantidad}` en sesión. Existía `views_checkout.py`, que llamaba al SDK de Mercado Pago directamente desde la vista. | App de Django completa (`apps.py`, `__init__.py`, `services.py`, `tests.py`). El carrito ahora guarda `{variant_id: cantidad}` con control de versión (`CART_VERSION`) para invalidar carritos con el formato viejo sin romper la sesión del usuario. `views_checkout.py` **se eliminó**: el checkout ahora vive en la nueva app `orders`. |
| `orders` | **No existía.** | Nueva. `Order`, `OrderItem`, `Address`. Servicios de creación de pedido, confirmación de pago, transición de estados. |
| `payments` | **No existía.** El pago se resolvía con una llamada directa al SDK de `mercadopago` desde `carrito/views_checkout.py`. | Nueva. `PaymentTransaction`, interfaz abstracta de proveedor (`PaymentProvider`), implementación simulada (`MockPaymentProvider`) e implementación real (`MercadoPagoPaymentProvider`) sobre el cliente ya existente en `integrations/mercadopago/`. Webhook con verificación de firma HMAC. |
| `inventory` | **No existía.** El único dato de stock era `Product.stock`, un entero plano por producto (no por talla/color), y nada en el flujo de compra lo tocaba. | Nueva. `Inventory` por variante, con decremento atómico a nivel de base de datos (`UPDATE ... WHERE quantity_available >= cantidad`) para que dos compras simultáneas de la última unidad no puedan vender de más. |
| `shipping` | **No existía.** El envío no se calculaba ni se mostraba de forma consistente. | Nueva. Cotización simulada con umbral de envío gratis, persistida en el pedido. |
| `administracion` (GoToGymAdmin) | Gestionaba productos/categorías/marcas básicas. | Se le agregó gestión de variantes, medios, pedidos y transacciones de pago (`orders.html`, `order_detail.html`, `payment_transactions.html`, `variants.html`, todas nuevas). |

### 2.2. El cambio más importante: cómo se procesa una compra

**Antes** (`gotogym/carrito/views_checkout.py`, eliminado — texto real del archivo en el commit `1f18d84`):

```python
@login_required(login_url='/accounts/acceso/')
def checkout(request):
    cart = request.session.get('cart', {})
    productos = Product.objects.filter(id__in=cart.keys())
    preference_items = [...]
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    preference_response = sdk.preference().create(preference_data)
    return redirect(preference["init_point"])
```

Ningún registro propio se creaba antes de mandar al usuario a pagar. Si el pago se aprobaba, no había ningún mecanismo que lo confirmara del lado de GoToGym: `auto_return: "approved"` simplemente devolvía al usuario al carrito. No se descontaba stock en ningún punto. El precio se tomaba de `producto.price` en el momento del checkout, así que si el precio cambiaba entre el checkout y la confirmación, no había ningún registro de cuál fue el precio real cobrado.

**Ahora** (`orders/services.py`, `payments/views.py`):

1. `create_order_from_cart` valida el carrito contra la base de datos real (no contra lo que diga la sesión), crea un `Order` con estado `pending_payment` y congela en cada `OrderItem` el nombre, SKU, talla, color y precio **en ese momento** (snapshot), antes de que exista ningún intento de pago.
2. Recién ahí se crea el intento de pago (`PaymentTransaction`) y se redirige al proveedor.
3. `confirm_payment` es el único punto de entrada que decrementa inventario, y solo se ejecuta cuando el pago queda `approved` — vía el webhook real de Mercado Pago (verificado con firma HMAC) o, en desarrollo, vía el panel de simulación.
4. La idempotencia se protege con el estado del **pedido** (`order_status`), no con el estado del pago: si el webhook llega dos veces, la segunda llamada no vuelve a descontar stock.

### 2.3. Configuración: dos riesgos reales del original, corregidos

**Riesgo 1 — sin `DATABASE_URL` ni variables `MYSQL_*`, el proyecto apuntaba a un host de producción por defecto.** `gotogym/settings.py` en `1f18d84`:

```python
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            ...
            'HOST': os.environ.get('MYSQL_HOST', 'servergotogym.mysql.database.azure.com'),
        }
    }
```

No existía ninguna rama de SQLite. Cualquier entorno sin configurar caía, por defecto, en un intento de conexión a un host de Azure con nombre fijo. El mismo patrón aparecía en `environments/backend/.env.test.example`, que declaraba ese mismo host como base de datos para las validaciones de backend. **Ahora** `settings.py` resuelve en orden `DATABASE_URL` (Postgres, el motor objetivo) → `MYSQL_*` (heredado, solo si se declara explícitamente) → SQLite local sin configuración — nunca un host remoto por defecto — y los `.env.example` ya no mencionan ese host.

**Riesgo 2 — no había ningún seguro entre agregar al carrito y el navegador.** Las mutaciones de carrito no forzaban `POST`, y el checkout llamaba al SDK de pago sin ningún control de tasa. Ahora `add_to_cart` exige `POST` + CSRF + `@rate_limit`, y lo mismo el endpoint de simulación de pagos.

### 2.4. Seguridad y verificación externa (nuevo, no existía nada equivalente)

- Firma HMAC del webhook de Mercado Pago (`payments/signature.py`), verificada contra la documentación real del proveedor (no asumida).
- El webhook está registrado **fuera** de `i18n_patterns` (`gotogym/urls.py`) a propósito: un webhook real de un tercero no antepone `/es/` a la URL, y dentro de `i18n_patterns` habría sido inalcanzable.
- `PAYMENTS_MOCK_UI_ENABLED`: el panel de simulación de pagos (útil en desarrollo) se puede desactivar explícitamente y nunca debe quedar accesible en producción real — ver sección 8.

---

## 3. Frontend

### 3.1. Plantillas de comercio: alcance del cambio

`git diff --stat` sobre las plantillas de `tienda` (las dos únicas que ya existían) por sí solo muestra **301 líneas modificadas en `producto_detail.html`** y **282 en `producto_list.html`** — prácticamente una reescritura completa, no un ajuste. A eso se suman plantillas enteramente nuevas: `carrito/cart_detail.html` (reescrita para variantes), y las de `orders`/`payments` (`checkout.html`, `my_orders.html`, `order_detail.html`, `pending.html`), que no existían porque esas apps no existían.

**Antes:** selectores `<select>` para elegir producto, sin variantes reales, sin galería, sin selector visual de talla/color, sin badges de disponibilidad basados en datos reales.

**Ahora:** grid de tarjetas con filtros y paginación en PLP; en PDP, tallas y colores como botones (no dropdown), galería tipo carrusel con miniaturas y navegación por teclado, disponibilidad verificada contra inventario real por variante, y un carrito/checkout que muestra el mismo total que se cobra.

### 3.2. Sistema de diseño: de valores sueltos a tokens reconciliados

El dominio comercial no tenía ningún sistema de color propio — heredaba el tema oscuro Quantum (`style.css`) de forma incidental y sin ningún ajuste. Se construyó `static/css/tokens.css` (nuevo) con:

- `--color-zafiro: #17375C` — el hex oficial del Brand Book (verificado contra el modelo `ColorMarca`, que documenta la paleta pero nunca se conectó a ningún context processor real).
- `--color-premium-white: #F8F9FA` — reemplaza el blanco genérico de Tailwind en las 7 plantillas de comercio.
- `--color-ink: #101012` — corrige un bug real de contraste (texto blanco heredado del tema oscuro, invisible sobre las superficies claras del catálogo) que se descubrió durante este trabajo, no que existiera documentado antes.

### 3.3. Componentización (no existía ningún partial reutilizable)

`_product_card.html`, `_price.html`, `_price_row.html`, `_cta_button.html`, `_badge.html`, `_size_selector.html`, `_color_selector.html`, `_media_gallery.html` — ocho piezas nuevas que eliminaron HTML duplicado entre PLP, PDP, carrito y checkout. Antes de esto, cambiar el estilo de un botón de "Añadir al carrito" requería editar cada plantilla por separado.

### 3.4. Identidad Quantum: integración inicial, todavía parcial

Se auditó explícitamente contra los manuscritos (`docs/ecomerce/Auditoria_Visual_Quantum_vs_Manuscritos.md`) y se encontró que el dominio comercial no tenía **ninguna** conexión visual con Quantum — ni siquiera el acento turquesa característico. Se corrigió parcialmente: el símbolo original de marca (el mismo PNG de Home) ahora aparece en el header compartido de todo el comercio, con un halo turquesa que respira suavemente, y la galería de la PDP tiene un acento ambiental sutil del mismo color. Esto todavía no es una integración completa de marca; el propio documento de auditoría deja pendientes explícitos (ver sección 7).

### 3.5. Navegación, carrito visible y footer

- El acceso al carrito estaba escondido dentro del menú de tres rayas y **el contador de unidades nunca funcionó**: el context processor que lo calculaba (`carrito/context_processors.py`) existía en el código pero jamás se había registrado en `TEMPLATES` de `settings.py`, así que siempre mostraba el valor por defecto (0). Se corrigió el registro, se movió el ícono de carrito al header (visible siempre, no solo en el menú móvil), y se verificó que el contador refleja unidades reales sumadas correctamente a través de todas las páginas.
- La home pública/autenticada ahora redirige al usuario con sesión activa a `/welcome/` en vez de mostrarle otra vez la pantalla de login/registro (resuelto en la vista, no en cada plantilla, para que cubra el logo, el menú móvil y cualquier enlace futuro sin repetir la condición).
- El footer se reorganizó: los 9 enlaces legales pasaron de una lista vertical a una fila horizontal centrada con área de toque propia por enlace, y los íconos de redes sociales crecieron de 18px a 56px (los glifos, de 14px a 26px).

---

## 4. Base de datos

### 4.1. Tablas nuevas

| Tabla | App | Propósito |
|---|---|---|
| `ProductVariant` | products | Unidad vendible real: SKU, talla, color, precio propio opcional. |
| `ProductMedia` | products | Múltiples imágenes por producto (antes: una sola, campo plano en `Product`). |
| `Inventory` | inventory | Stock por variante, no por producto. |
| `Order`, `OrderItem`, `Address` | orders | Pedido persistente con snapshot de precio/producto al momento de la compra. |
| `PaymentTransaction` | payments | Registro de cada intento de pago, su proveedor, estado e idempotency key. |
| `ShippingQuote` | shipping | Cotización de envío persistida junto al pedido. |

### 4.2. Migraciones nuevas (12 en total)

| Migración | Tipo | Nota para producción |
|---|---|---|
| `products/0007_rename_price_base_price` | Esquema | Renombra una columna existente; segura y necesaria en cualquier entorno. |
| `products/0008_productvariant_productmedia_and_more` | Esquema | Crea las tablas nuevas; aditiva. |
| `products/0009_seed_variants_and_media` | **Datos, re-ejecutable** | Genera variantes/medios a partir de **cualquier** producto que ya exista en la base (no solo del catálogo semilla). Segura para producción: es un backfill, no inserta productos demo. |
| `inventory/0001_initial`, `0002_seed_inventory_from_product_stock` | Esquema + datos | La segunda reparte `Product.stock` (un entero por producto) entre las variantes generadas. Es una aproximación explícita, documentada como tal en el propio archivo — no es una medición real de inventario por variante. |
| `orders/0001_initial`, `0002_order_internal_note` | Esquema | Aditivas. |
| `payments/0001_initial` | Esquema | Aditiva. |
| `shipping/0001_initial` | Esquema | Aditiva. |
| `products/0004_seed_gotogym_catalog` (**pre-existente en `1f18d84`, no nueva**) | Datos | Se menciona aquí porque es la única migración de las 12 anteriores que **inserta productos de demostración con nombre fijo**. Si la base de datos de producción ya tiene su propio catálogo, ejecutar el pipeline completo de migraciones agregaría esos 7 productos semilla junto al catálogo real. Ver sección 8. |

### 4.3. Motor de base de datos

Sin cambios de motor: sigue siendo PostgreSQL en producción (`DATABASE_URL`), MySQL heredado si se declara explícitamente, SQLite en local. El cambio real es que **ahora existe una ruta segura sin configuración** (SQLite local) en vez de un fallback a un host de Azure fijo — ver sección 2.3.

---

## 5. Funcionalidades agregadas (checklist completo)

- [x] Catálogo con variantes reales (talla/color/SKU/precio propio opcional).
- [x] Galería de múltiples imágenes por producto (aunque hoy el catálogo real solo tiene 1 imagen por producto — la capacidad existe, el contenido fotográfico no).
- [x] Filtros de PLP por categoría, talla, color y precio, basados en disponibilidad real.
- [x] Selector de talla/color como botones en PDP, con disponibilidad verificada en vivo.
- [x] Carrito basado en variante (no en producto), con reinicio seguro de carritos con formato antiguo.
- [x] Checkout de un solo paso, con dirección de entrega y resumen de costos completo.
- [x] Pedido persistente (`Order`) creado antes de cualquier intento de pago.
- [x] Snapshot de precio/producto en cada `OrderItem` (protege contra cambios de precio posteriores).
- [x] Inventario por variante con decremento atómico (protección contra sobreventa por concurrencia).
- [x] Restitución de stock si un pedido se cancela después de haberlo descontado.
- [x] Proveedor de pago simulado (`MockPaymentProvider`) para desarrollo y demostraciones.
- [x] Proveedor de pago real (`MercadoPagoPaymentProvider`) integrado y listo, pendiente de credenciales de producción.
- [x] Webhook de Mercado Pago con verificación de firma HMAC real.
- [x] Cálculo y persistencia de envío, con umbral de envío gratis.
- [x] "Mis pedidos" y detalle de pedido para el cliente.
- [x] Panel de administración: gestión de variantes, medios, pedidos y transacciones de pago.
- [x] Límite de tasa (`rate_limit`) en endpoints sensibles (agregar al carrito, simular pago).
- [x] Sistema de tokens de color reconciliado contra el Brand Book real.
- [x] Componentización de plantillas de comercio (8 partials reutilizables).
- [x] Contador de carrito visible y funcional en el header (antes escondido y roto).
- [x] Redirección de home a la sesión activa cuando corresponde.
- [x] Integración inicial (parcial) de la identidad Quantum en el dominio comercial.
- [ ] Activación real de Mercado Pago (arquitectura lista, nunca probada con credenciales reales).
- [ ] Traducción de las cadenas nuevas del dominio comercial a inglés/portugués.
- [ ] Todo lo que sigue en `Roadmap_Ecommerce_GoToGym_SHOP_Fase2.md` (ver sección 7).

---

## 6. Calidad y pruebas

| | `1f18d84` | Actual |
|---|---|---|
| Tests del dominio de comercio | 0 (no existía el dominio) | 265 (241 vía `manage.py test` + 24 de `administracion`, que vive físicamente en `GoToGymAdmin/` y por eso necesita invocarse aparte) |
| Verificación de integridad de datos | Ninguna herramienta | `products/management/commands/audit_catalog.py` (auditoría de catálogo/inventario/medios huérfanos) |
| Aislamiento de tests | Base de datos en memoria (comportamiento por defecto de Django), pero `MEDIA_ROOT` **no** aislado — se descubrió y corrigió un caso real de archivos de prueba escribiéndose en `media/products/` durante la suite de `administracion` | Aislado explícitamente con `MEDIA_ROOT` temporal donde aplica |
| Script de validación de backend | Corría `manage.py test` a secas — nunca ejecutaba los tests de `administracion` (invisibles a la raíz del proyecto) | `run_backend_checks.sh` ejecuta ambos comandos explícitamente |

---

## 7. Cómo se proyecta continuar: roadmap por fases

Este informe no repite el contenido completo de los dos roadmaps ya existentes en `docs/ecomerce/`; los resume para dar continuidad:

**`Roadmap_Ecommerce_GoToGym_SHOP_v2.md`** — el roadmap que ya se ejecutó por completo (Sprint 0 a Sprint 18): construyó todo el dominio transaccional descrito en las secciones 2, 4 y 5 de este informe. Cerrado.

**`Roadmap_Ecommerce_GoToGym_SHOP_Fase2.md`** — el roadmap vigente, todavía en ejecución parcial. Define 11 sprints de doble carga que los de v2, organizados en cinco bloques, en este orden:

1. **Fundamentos visuales** (F2-1 tokens de color, F2-2 componentización) — **completos**, descritos en la sección 3 de este informe.
2. **Home y navegación** (F2-3: Home product-first, navegación persistente) — **pendiente**. Home sigue siendo la pantalla login-first que el roadmap identificó como el hallazgo #1 desde el inicio.
3. **PLP/PDP premium** (F2-4 badges y búsqueda, F2-5 narrativa y galería real) — **pendiente**.
4. **Motion, carrito como drawer, accesibilidad y rendimiento medidos** (F2-6, F2-7) — **pendiente**; parte del trabajo de motion/Quantum de esta semana adelanta piezas sueltas (halo del logo, acento en la PDP), pero el bloque completo no se ha ejecutado.
5. **Funcionalidades diferenciadoras** (F2-8 analítica de funnel, F2-9 wishlist, F2-10 Alta Costura guiada, F2-11 reseñas verificadas + activación real de Mercado Pago) — **pendiente**.

Adicionalmente, `Auditoria_Visual_Quantum_vs_Manuscritos.md` documenta un ajuste de criterio ya aplicado: el dorado del Brand Book se probó como color reservado para la categoría "Alta costura" y se revirtió el mismo día — en una grilla de productos, un botón de color distinto se lee como error, no como jerarquía. El dorado quedó sin rol asignado en el catálogo, a la espera de un lugar donde de verdad comunique exclusividad (candidato natural: el flujo de personalización del Sprint F2-10).

---

## 8. Qué revisar y probar antes de enviar a producción

Esta sección es la que se pidió explícitamente. Se ordena de mayor a menor impacto.

### 8.1. Bloqueantes (no debería salir a producción sin resolver esto)

1. **Mercado Pago real nunca se probó de punta a punta.** Toda la verificación de pagos se hizo contra `MockPaymentProvider`. Antes de activar `PAYMENT_PROVIDER=mercadopago` en producción:
   - Conseguir credenciales de **sandbox** primero (`MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`) y correr un ciclo completo real: crear preferencia → pagar en el checkout de Mercado Pago → recibir webhook → confirmar que `confirm_payment` decrementa stock exactamente una vez.
   - Registrar la URL del webhook (`/pagos/webhook/mercadopago/`, fuera de `/es/` o `/en/`) en el panel de Mercado Pago.
   - Recién después, repetir con credenciales de producción.
2. **`PAYMENTS_MOCK_UI_ENABLED` debe quedar en `false` (o sin declarar) en producción.** El panel de simulación de pagos nunca debe ser accesible fuera de desarrollo.
3. **El límite de tasa no es confiable con más de un worker.** `gotogym/gotogym/ratelimit.py` usa la caché por defecto de Django (`LocMemCache`), que vive dentro de cada proceso. El `Dockerfile` de este mismo proyecto arranca Gunicorn con `--workers 3`: en la práctica, el límite real permitido es hasta 3 veces el configurado, repartido según a qué worker caiga cada request. Antes de producción: configurar una caché compartida (Redis/Memcached) para `CACHES['default']`, o aceptar explícitamente esta limitación si el riesgo es tolerable.
4. **Decidir qué hacer con `products/0004_seed_gotogym_catalog`.** Si la base de datos de producción va a arrancar con el catálogo real de la tienda (no el catálogo de 7 productos semilla usado en desarrollo), esta migración (que ya existía en `1f18d84`, no es nueva) insertaría esos 7 productos de demostración junto al catálogo real. Revisar antes de correr `migrate` contra la base de producción por primera vez.
5. **Backup de la base de datos antes de correr las 12 migraciones nuevas**, en particular `inventory/0002_seed_inventory_from_product_stock` (reparte stock existente entre variantes nuevas) y `products/0009_seed_variants_and_media` (genera variantes desde texto libre con heurística — el propio comando de auditoría ya señala productos que quedan con una variante genérica "UNICA/UNICO" que requiere revisión manual, ej. "X5 Generation Mujer" en los datos de desarrollo).

### 8.2. Alto impacto, no bloqueante pero debe hacerse pronto

6. **Traducciones incompletas.** Hay 66 cadenas nuevas (`{% trans %}`) en el dominio comercial que no existen en ningún archivo `.po` (`locale/en/LC_MESSAGES/django.po` y `locale/pt/...` solo tienen 59 msgids en total, todos anteriores a este trabajo). En inglés/portugués, todo el Store/checkout/pedidos/pagos se muestra en español (comportamiento por defecto de Django ante un msgid sin traducción, no un error, pero sí una experiencia incompleta para esos dos idiomas). Ejecutar `makemessages` y traducir antes de anunciar el sitio como multi-idioma.
7. **Verificar `collectstatic` sobre los archivos nuevos**, en particular `static/css/tokens.css` (nunca tuvo query de versión hasta este trabajo) y las plantillas de `tienda/templates/tienda/partials/` — confirmar que el pipeline de despliegue las recoge igual que el resto.
8. **Accesibilidad y rendimiento reales, no solo revisados en el código.** No hay navegador disponible en este entorno de desarrollo; todo lo relacionado con contraste, foco de teclado y Core Web Vitals se verificó por inspección de CSS/HTML, no con herramientas como axe-core o Lighthouse contra una página real. Correrlas antes de dar por cerrada la fase visual.
9. **Verificación visual humana de los cambios más recientes** (footer, logo con halo Quantum, contador de carrito): se verificó que el HTML/CSS servido es correcto por inspección de contenido, pero ningún cambio de esta semana se vio renderizado en un navegador real durante el desarrollo — vale la pena una revisión visual antes de considerar esta parte terminada.

### 8.3. Antes de la primera venta real

10. Confirmar que las 7 fotos de producto actuales (una por producto, sin galería real) son aceptables para el lanzamiento, o reemplazarlas — el modelo ya soporta múltiples imágenes por producto (`ProductMedia`), pero el contenido fotográfico no existe todavía.
11. Confirmar el umbral de envío gratis y el proveedor de envío real (`shipping/services.py` usa una cotización simulada, no una tarifa de un transportista real).
12. Revisar `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` y `CSRF_COOKIE_SECURE` en las variables de entorno del release de producción (`environments/azure/.env.release.example` ya las lista; confirmar que el entorno real las declara con los valores correctos, no solo los de ejemplo).
13. Ejecutar `environments/backend/run_backend_checks.sh` completo contra el entorno de staging final, no solo en local.

---

## 9. Riesgos conocidos y decisiones pendientes (no técnicas)

- **Home sigue siendo login-first.** Ningún trabajo de esta fase la tocó todavía; sigue siendo el hallazgo #1 documentado desde el primer análisis de los manuscritos.
- **La firma visual de Quantum en el dominio comercial es mínima** (un halo en el logo del header, un acento en la galería de la PDP). Es un punto de partida, no la integración completa que describen los manuscritos.
- **El catálogo de desarrollo tiene un producto ("X5 Generation Mujer") con una variante genérica** que el propio sistema de auditoría marca para revisión manual — no se le pudo asignar talla/color real por heurística de texto.
