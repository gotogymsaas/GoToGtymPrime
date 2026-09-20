# GoToGym SHOP — Auditoría de Fase 2 y Roadmap de diseño visual + funcionalidades

**Fecha de auditoría:** 19 de septiembre de 2026
**Estado de partida:** los 19 sprints de `Roadmap_Ecommerce_GoToGym_SHOP_v2.md` (Sprint 0 a Sprint 18) están completos e implementados en el código. Este documento **no reemplaza ni modifica** ese roadmap: lo da por cerrado y define la fase siguiente.
**Fuentes:** código real del repositorio (inspección directa post-Sprint 18) · `Manuscrito_Rediseno_Competitivo_GoToGym_SHOP.pdf` · `Manuscrito_Direccion_Diseno_GoToGym_SHOP.pdf` · `Roadmap_Ecommerce_GoToGym_SHOP_v2.md` (como registro de lo ya decidido y ya construido).
**Regla de verdad:** igual que en v2, cuando el código y los manuscritos difieren, este documento parte del código. Los manuscritos son la fuente de requisitos visuales/funcionales; no se reinterpretan ni se suavizan.

---

# 1. Resumen ejecutivo

El MVP transaccional está terminado y probado: catálogo con variantes, inventario transaccional con protección de concurrencia, checkout con `Order` persistente antes del pago, proveedor de pago simulado con arquitectura lista para Mercado Pago real, envío calculado, panel de administración de pedidos/catálogo, cuenta del cliente y políticas mínimas. Esto es exactamente el prerequisito que el manuscrito de dirección de diseño exige antes de construir la capa visual: *"El Store competitivo requiere un modelo de producto con variantes y medios múltiples, además de Order, Payment, Shipping y reconciliación. El frontend no puede compensar indefinidamente un dominio comercial insuficiente"* (Dirección de Diseño, §15). Ese dominio ya no es insuficiente.

Lo que audita este documento es la otra mitad de ambos manuscritos, la que v2 dejó **explícitamente fuera de su alcance** por diseño (v2 se ocupó del dominio transaccional, no del rediseño visual de Home/PLP/PDP como experiencia de marca). El resultado de la auditoría es claro y verificado contra el código real:

1. **La Home pública sigue siendo login-first**, exactamente el hallazgo que ambos manuscritos señalan como el problema P0 original. Ningún sprint de v2 la tocó, porque no estaba en su alcance.
2. **Existen dos sistemas de color sin relación entre sí**, verificado con evidencia: el sistema "Quantum" original (`static/css/style.css`, tokens `--color-*`) y los valores sueltos que yo mismo introduje en los Sprints 5-14 (`#093f62`, `#C5A46B`, escritos directamente en cada plantilla). Esto es, con evidencia de código, el hallazgo que el manuscrito predice: *"Home/Store/PDP/Cart parecen productos distintos"*.
3. **El dominio comercial nuevo no tiene componentes visuales reutilizables**: cada plantilla de `tienda`, `orders`, `payments` y `carrito` repite HTML propio en vez de compartir partials.
4. **El carrito es una página completa, no el drawer/mini-cart** que ambos manuscritos piden para no sacar al usuario del catálogo.
5. **La ficha de producto no tiene la narrativa ni la galería que el manuscrito exige** (6+ medios objetivo; hoy el 100% del catálogo tiene exactamente 1 imagen por producto).
6. **No existe instrumentación de analítica de funnel**, ni sistema de búsqueda con sugerencias, ni personalización de Alta Costura como flujo guiado, ni reseñas verificadas, ni wishlist.

Este documento propone una **Fase 2** de 11 sprints de ~6 días cada uno (el doble de duración/carga que los sprints de v2, que eran de 3 días), organizados en cinco bloques: fundamentos visuales, Home y navegación, PLP/PDP premium, motion/carrito/accesibilidad/rendimiento, y funcionalidades diferenciadoras — en ese orden, porque es el orden que el propio manuscrito de dirección de diseño recomienda explícitamente (*"No comenzar por una animación hero compleja. Primero estabilizar modelo de compra y design system; después construir la narrativa inmersiva"*, §14).

---

# 2. Metodología de la auditoría

Para cada afirmación de este documento se verificó el código real, no solo la memoria de lo construido en v2:

- Se releyeron íntegros ambos manuscritos (95 y 15 páginas respectivamente) para no perder ningún requisito visual de las secciones 5-16 del manuscrito de dirección de diseño (motion, gamificación, ilustración/video, design system, backend, experimentación, Anexo A).
- Se auditó con `grep` el uso real de color en las plantillas nuevas (`tienda`, `orders`, `payments`, `carrito`) contra los tokens ya definidos en `static/css/style.css`.
- Se verificó con consultas directas a la base de datos local (`db_local.sqlite3`) cuántas imágenes (`ProductMedia`) tiene realmente cada producto del catálogo.
- Se verificó la ausencia de campos/modelos (`created_at` en `Product`, cualquier modelo de evento de analítica) antes de afirmar que no existen.
- Se contrastó cada renglón del Anexo A del manuscrito de dirección de diseño ("Especificación de diseño no negociable") contra el estado real, uno por uno.

---

# 3. Lo que el manuscrito exige y que v2 ya resolvió (no se repite en Fase 2)

Antes de auditar lo que falta, hay que ser justos con lo que ya está. La tabla `12. Evolución del backend` del manuscrito de dirección de diseño pide un modelo mínimo de: `Product` (padre) con `ProductVariant` (SKU, color, talla, precio, stock), `ProductMedia`, `CartService`, `Order`/`OrderItem` con snapshot, `Payment` con proveedor/estado/idempotency key, `Shipping` con dirección/método/costo/ETA. **Esto existe, íntegro, probado con 265 tests, y en producción de código desde los Sprints 3, 4, 7, 8, 9 y 10 de v2.** No hay ninguna tarea de dominio comercial pendiente en este documento: todo lo que sigue es capa visual y funcionalidades de diferenciación sobre una base ya sólida.

También están resueltos, y no se repiten: retiro de influencers del journey comercial (§10.2 del manuscrito competitivo, Sprint 1 de v2), moneda única COP de punta a punta (Sprint 1 y 10), `POST`/CSRF en mutaciones de carrito (Sprint 1 y 7), tallas como botones y color visible en PDP (Sprint 6), stock real por variante en vez de un campo plano (Sprint 3-4), orden persistida antes del pago (Sprint 8), envío incluido en el total único (Sprint 10), y arquitectura de Mercado Pago real preparada sin activar (Sprint 18).

---

# 4. Auditoría visual detallada

## 4.1. Sistema de color: dos marcas conviviendo sin saberlo

**Hallazgo verificado.** `static/css/style.css` (el sistema "Quantum" que ya existía antes de cualquier sprint de comercio) define tokens propios:

```css
--color-bg-base: #0d0d0f;
--color-accent: #00d4c7;
--color-gold: #d4b46a;
--color-text-primary: #ffffff;
```

Las plantillas de comercio que se construyeron en v2 (`tienda/`, `orders/`, `payments/`, `carrito/`) **no usan ninguno de estos tokens**. Usan valores hexadecimales escritos a mano, repetidos decenas de veces:

```
#093f62   (azul, no está definido en el Brand Book ni en ningún token existente)
#C5A46B   (dorado, distinto del --color-gold: #d4b46a ya definido)
```

Esto es exactamente la advertencia del manuscrito de dirección de diseño: *"El diseño visual debe convertirse en tokens, no en valores dispersos... Esto permite que Home, Store, Blog/Journal y PDP dejen de verse como productos diferentes"* (§11), y el hallazgo de la tabla de diagnóstico: *"Design language inconsistente: Home/Store/PDP/Cart parecen productos distintos"* (§3). No es una hipótesis: hoy, en este repositorio, Home y Store literalmente usan dos paletas de azul/dorado distintas que nunca se reconciliaron.

**No hay ningún archivo de tokens de movimiento** (`--motion-fast`, `--motion-ui`, `--motion-story`) ni de espaciado/radio/sombra unificado que el manuscrito pide en la tabla de la sección 11.

## 4.2. Home pública y autenticada: siguen siendo login-first

`gotogym/templates/home.html`, verificado línea por línea: los dos CTA primarios del primer viewport son *"Iniciar Sesión"* y *"Crear cuenta"*. No hay producto visible, no hay categoría visible, no hay ninguno de los CTAs que el manuscrito pide (*"Comprar Mujer"*, *"Comprar Hombre"*, *"Personalizar mi prenda"*). Esto es, verbatim, el hallazgo #1 de ambos manuscritos, sin resolver, porque v2 nunca tuvo el rediseño de Home en su alcance (v2 se enfocó en el dominio transaccional).

`logged_home.html` tiene el mismo problema en menor grado: el saludo y el orbe Quantum dominan la pantalla; los accesos a Store/Blog/Contacto son enlaces secundarios de texto plano, no una navegación real.

## 4.3. Navegación: no existe una arquitectura de información persistente

No hay, en ninguna plantilla, una barra de navegación con "Novedades, Mujer, Hombre, Alta Costura, Tecnología, Buscar, Cuenta, Carrito" (manuscrito competitivo §8.1; manuscrito de dirección §6). La navegación actual (`base.html`) es un menú de cuenta desplegable más un menú móvil con cuatro enlaces sueltos (Carrito, Store, Blog, Contacto). No hay mapeo de las categorías reales (`Sport Premium`, `Conjuntos`, `Semi Personalizada`, `Alta costura personalizada exclusiva`) a una navegación por audiencia/actividad.

## 4.4. PLP: la base está, falta la capa premium

**Lo que sí se cumple** (construido en Sprint 5 de v2): grid visual de 2-4 columnas reemplazando los selectores; filtros reales por talla/color/categoría/precio basados en disponibilidad real; distintivo "Agotado"; paginación. Esto satisface la hipótesis H2 del programa experimental del manuscrito (*"Grid PLP con filtros"* vs. dropdown).

**Lo que falta**, verificado contra el código de `producto_list.html`:
- No hay badges de "Nuevo", "Personalizable" ni "Best seller" (el manuscrito los pide explícitamente en §8.2; `Product` ni siquiera tiene un campo `created_at` para poder calcular "Nuevo").
- No hay chips de filtros activos con opción de limpiar cada uno por separado.
- La búsqueda es un campo de texto simple (`filtro`), sin autocompletado ni sugerencias.
- Las tarjetas no tienen una segunda imagen al pasar el cursor (hoy es imposible: cada producto tiene exactamente 1 `ProductMedia`, verificado contra la base real).
- No hay contenido editorial (looks, comprar por actividad, tecnología textil) intercalado, que el manuscrito pide como módulos de Home pero que también aplican como cabecera de PLP.

## 4.5. PDP: selectores reales, pero sin narrativa ni confianza

**Lo que sí se cumple** (Sprint 6 de v2, y verificado como no negociable en el Anexo A del manuscrito de dirección): tallas como botones (no dropdown), color visible como swatch, un único CTA dominante, sin datos simulados (se retiraron las estrellas falsas y los campos inexistentes).

**Lo que falta**, y es sustancial:
- **Galería**: el Anexo A pide "6+ medios objetivo en PDP premium". Verificado contra la base real: **el 100% de los productos tiene exactamente 1 imagen.** No es una tarea solo de código: requiere fotografía nueva (frontal, posterior, detalle de tejido, fit) que hoy no existe.
- **Narrativa del producto**: no hay sección "Por qué fue creada", ni materiales/tecnología explicados separando lo medido de lenguaje de marca (§10.3), ni guía de talla/fit, ni cuidado.
- **Trust row cerca del CTA**: el Anexo A lo exige explícitamente ("entrega/cambios cercanos"); hoy el CTA de "Añadir al carrito" no tiene ninguna mención de tiempo de entrega ni enlace a política de cambios junto a él (las políticas sí existen desde el Sprint 14 de v2, pero no están enlazadas desde la PDP).

## 4.6. Carrito y checkout: página completa, no drawer

Ambos manuscritos piden explícitamente un carrito tipo *drawer* en escritorio y *bottom sheet*/pantalla completa en móvil, "sin sacar al usuario inmediatamente del catálogo" (Dirección de Diseño §7.5). Hoy, `carrito:cart_detail` es una página independiente a la que el usuario navega y desde la que tiene que volver atrás. No hay mini-cart, no hay confirmación localizada de "añadir al carrito" (el `add_to_cart` de la PDP hace un `POST` normal con recarga de página en el flujo estándar del formulario, aunque el JS de la PLP sí usa `fetch` con actualización del contador).

El checkout de un solo paso ya cumple la recomendación de "menor número de pasos posible", pero exige login — una divergencia **ya documentada como decisión de negocio en v2** (ver §7 de este documento).

## 4.7. Componentización: cero partials compartidos

`tienda/templates/tienda/producto_list.html`, `producto_detail.html`, `orders/templates/orders/checkout.html`, `carrito/templates/carrito/cart_detail.html` repiten cada uno su propio HTML para tarjetas de producto, precios, badges y botones CTA. No existe ni un solo `{% include %}` de un partial reutilizable entre ellos. Esto contradice directamente la tabla de "Componentes" del manuscrito (§11: `ProductCard`, `Price`, `Swatch`, `SizeSelector`, `Badge`, `CTA`, `TrustRow`, `MediaGallery` como piezas reutilizables) y es la causa técnica directa del hallazgo de §4.1 (si el precio se pinta con `${{ x|floatformat:0 }}` copiado y pegado seis veces, seis lugares pueden divergir en formato y color).

## 4.8. Motion / "game feel": casi inexistente

Lo único implementado (Sprint 17 de v2): transiciones de `hover` en tarjetas y botones, y una regla global de `prefers-reduced-motion`. **No existe** ninguna de las microinteracciones que el manuscrito pide explícitamente en su tabla de animaciones recomendadas (§8): crossfade al cambiar de color, microescala 1.02 al seleccionar talla, confirmación localizada de "añadir al carrito" sin salir de la página, drawer que conserva contexto. No hay violación de la regla de "motion budget" porque, sencillamente, casi no hay motion que auditar.

## 4.9. Accesibilidad: parcial, sin herramienta automatizada real

Lo hecho en Sprint 17 de v2 es real pero manual: foco visible con `focus:ring`, `aria-live` en la disponibilidad de variante, un error de contraste AA corregido con evidencia (dorado sobre blanco en PDP). **No se ha ejecutado ninguna auditoría automatizada** (axe-core, Lighthouse) porque el entorno de ejecución de este proyecto no tiene navegador disponible — se documentó honestamente como limitación en su momento, y sigue siéndolo.

## 4.10. Rendimiento: sin pipeline de imágenes responsive

Existe `loading="lazy"` y contenedores con `aspect-ratio` fijo para evitar CLS, pero no hay `srcset`, no hay conversión a WebP/AVIF, y no puede haberla con el pipeline actual: `ProductMedia.image` guarda un único archivo tal cual se sube, sin generar variantes de tamaño. No se ha medido Core Web Vitals contra ningún entorno real (local o desplegado); el manuscrito pide LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 en p75 como objetivo operativo (Anexo A), y hoy no hay ningún dato, ni siquiera aproximado, sobre estas métricas.

---

# 5. Auditoría funcional detallada

| Capacidad (fuente: ambos manuscritos) | Estado | Evidencia |
|---|---|---|
| Personalización / Alta Costura como journey guiado | **No hecho** | `PersonalizationRequest` no existe; "X5 Generation" se vende como producto normal de variante única |
| Reseñas verificadas (`Review` + `OrderItem`) | **No hecho, correctamente diferido** | Ya había `OrderItem` desde v2 Sprint 8, que es el prerequisito que el manuscrito pedía para poder verificar compra real |
| Wishlist | **No hecho** | Sin modelo, sin botón en PLP/PDP |
| Promociones / cupones | **No hecho, fuera de alcance de v2 por decisión** | Sin modelo `Promotion` |
| Búsqueda con sugerencias | **Parcial** | Filtro de texto simple existe; sin autocompletado ni relevancia |
| Analítica de funnel / experimentación A/B | **No hecho** | Cero eventos instrumentados; `metricas` app existe pero es un dashboard interno de admin (posts/usuarios), no analítica de comprador |
| CRM / lifecycle (abandono de carrito) | **No hecho** | `crm/hubspot_config.py` existe pero no está conectado a ningún evento de `carrito` u `Order` |
| Activación real de Mercado Pago | **Preparado, no activo** (decisión de negocio) | `MercadoPagoPaymentProvider` completo desde v2 Sprint 18; requiere credenciales de producción que no existen |
| Guest checkout | **No hecho** (decisión de negocio explícita en v2 que contradice al Anexo A) | Ver §7, decisión pendiente #1 |
| Gamificación responsable (progreso/conocimiento/logro, sin dark patterns) | **No hecho** | Ninguna de las tres capas existe; tampoco hay ningún patrón oscuro que corregir |
| Ilustración técnica / video de producto | **No hecho** | Requiere activos nuevos, no solo código |

---

# 6. Anexo A del manuscrito de dirección de diseño — cumplimiento línea por línea

| Dimensión | Criterio de aceptación del manuscrito | Estado real |
|---|---|---|
| Producto | Producto visible en primer viewport; cards visuales; 6+ medios objetivo en PDP | **No** (Home login-first); PLP con cards ✅; PDP con 1 medio por producto ❌ |
| Cuenta | Navegación y carrito sin login; guest checkout prominente | **No cumplido, por decisión de negocio** — ver §7 |
| PDP | Tallas como botones, color visible, CTA único dominante, entrega/cambios cercanos | Tallas/color/CTA ✅ · entrega/cambios cercanos ❌ |
| Quantum | 10-15% del protagonismo visual en pantallas de decisión; sin bloquear interacción | Home aún es 80-90% Quantum; PLP/PDP ya son mayormente producto (✅ parcial) |
| Motion | reduced-motion; ninguna animación esencial depende de scroll; 1 foco animado dominante | reduced-motion ✅; sin animaciones "esenciales" que auditar porque casi no hay motion |
| Accesibilidad | WCAG 2.2 AA objetivo, teclado completo, focus visible, contraste verificado | Parcial, sin herramienta automatizada real |
| Rendimiento | LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 en p75 como target operativo | **Sin medir** |
| Backend | Variant, Order, Payment, Shipping antes de prometer UX avanzada de apparel | ✅ **Completo** (v2) |
| Influencers | fuera de Home/PLP/PDP/Cart/Checkout/Account de cliente | ✅ **Completo** (v2 Sprint 1) |
| Medición | funnel instrumentado antes de lanzamiento y pruebas de usuario por iteración | **No hecho** |

De diez dimensiones no negociables, **dos están completas** (backend, influencers — ambas resueltas en v2), **tres están parciales** (Quantum, accesibilidad, motion) y **cinco no están resueltas** (producto en primer viewport, guest checkout, entrega cerca del CTA, rendimiento medido, funnel instrumentado). Esa es la carga real de la Fase 2.

---

# 7. Decisiones de negocio pendientes (este documento no las resuelve solo)

1. **Login obligatorio vs. "navegación sin login" del Anexo A.** El roadmap v2 (decisión de negocio §4.3) exige login para todo Store, y ambos manuscritos recomiendan lo contrario. v2 ya documentó esto como "recomendación futura, no aplicada". Este documento **no reabre esa decisión**: la Fase 2 se diseña asumiendo que el login obligatorio sigue vigente, salvo que el negocio indique lo contrario antes de iniciar el Sprint F2-3 (Home) y el Sprint F2-9 (guest checkout). Si el negocio decide relajar esta regla, el Sprint F2-3 cambia de forma sustancial (la PLP pasaría a ser visible sin sesión, solo bloqueando el carrito).
2. **Inversión en fotografía y video nuevos.** La galería de 6+ medios por producto y el sistema de ilustración/video (§10 del manuscrito de dirección) no son tareas de código: dependen de que el negocio produzca o encargue ese contenido. Sin él, el Sprint F2-5 (PDP premium) queda con contenido de marcador de posición, no con la experiencia real que el manuscrito describe.
3. **Credenciales de sandbox de Mercado Pago.** Repetido de v2: sigue sin resolverse, y el Sprint F2-11 depende de ello para activar el proveedor real, aunque no bloquea el resto de la Fase 2.
4. **Alcance real de "Alta Costura".** El manuscrito propone un flujo de personalización con previsualización 2D/3D. Sin una decisión de negocio sobre qué tan lejos llega esa previsualización (¿ilustración estática por combinación, o configurador real?), el Sprint F2-10 se diseña con el nivel mínimo defendible (ilustración por combinación, sin render 3D).
5. **Prioridad de CRM/analítica frente a diseño.** Ambos son "funcionalidades", no visual — la Fase 2 los ubica al final por instrucción explícita de este encargo, pero si el negocio necesita medir conversión antes de invertir en rediseño visual, el orden de los bloques D y E podría intercambiarse.

---

# 8. Principios de la Fase 2 (heredados de los manuscritos, no inventados)

1. **Producto grande, interfaz pequeña.** Cada pantalla de decisión debe tener al producto como protagonista, no la identidad Quantum.
2. **Tokens, no valores dispersos.** Ningún color, tiempo de animación o espaciado nuevo se escribe suelto en una plantilla; se define una vez en el sistema de tokens y se referencia.
3. **Un componente, muchos lugares.** Ninguna pieza visual (tarjeta, precio, badge, CTA) se duplica entre PLP/PDP/Cart/Checkout.
4. **Evidencia antes que simulación.** Igual que en v2: ningún badge, review o dato se muestra si no sale de un modelo real.
5. **Un solo foco de movimiento por pantalla.** Regla de "motion budget" del manuscrito, aplicada literalmente.
6. **Nada de patrones oscuros.** Ninguna urgencia falsa, contador inventado o preselección oculta, ni siquiera en nombre de la conversión.
7. **Medir antes de decidir por opinión.** Ninguna mejora visual se declara "mejor" sin al menos un evento de analítica que lo respalde a futuro.
8. **No migrar a SPA.** El manuscrito lo dice explícitamente: Django + templates + JS progresivo sigue siendo suficiente; una migración solo se justificaría ante una necesidad funcional real, no por moda tecnológica.

---

# 9. Roadmap Fase 2 (sprints de ~6 días — el doble de los sprints de v2)

Notación de complejidad: **B**=baja, **M**=media, **A**=alta.

## Bloque A — Fundamentos visuales (antes de tocar ninguna pantalla)

### Sprint F2-1 — Sistema de tokens de diseño unificado (6 días · M)

**Objetivo:** un solo sistema de color/tipografía/espaciado/movimiento gobierna todo el sitio; cero valores hexadecimales sueltos en las plantillas de comercio.

**Dependencias:** ninguna (primer sprint de la fase).

**Tareas:**
- Reconciliar el Brand Book (`#101012` negro grafito, `#D4B46A` dorado fitness, `#0FBFB0` turquesa grafeno, azul zafiro, `#F8F9FA` blanco premium) con los tokens ya existentes en `style.css` (`--color-bg-base`, `--color-accent`, `--color-gold`) y con los valores sueltos de comercio (`#093f62`, `#C5A46B`). Decidir una única fuente de verdad; documentar la asignación de roles exactamente como la tabla de la sección 5.3 del manuscrito de dirección (grafito = base premium, blanco = catálogo, azul zafiro = texto funcional sobre fondo claro, dorado = exclusividad/alta costura, turquesa = estados tecnológicos sobre fondo oscuro).
- Crear `static/css/tokens.css`: variables de color, tipografía (escala display/H1/H2/body/labels de la sección 5.4), espaciado en grid de 8px, radios, sombras, y tokens de movimiento (`--motion-fast`, `--motion-ui`, `--motion-story`).
- Migrar **todas** las referencias de color sueltas en `tienda/`, `orders/`, `payments/`, `carrito/` a los tokens nuevos.
- Verificar y documentar contraste AA por combinación rol-de-color/fondo, replicando la tabla de contraste del manuscrito (dorado y turquesa nunca como texto pequeño sobre blanco).

**Base de datos:** ninguna.

**Tests:** ninguno automatizable (es CSS); checklist manual de que cada plantilla de comercio referencia solo tokens, verificado con `grep` de hexadecimales sueltos como criterio de salida (debe devolver cero resultados).

**Criterios de aceptación:** `grep -rn "#[0-9A-Fa-f]\{6\}"` sobre `tienda/templates`, `orders/templates`, `payments/templates`, `carrito/templates` no devuelve nada que no sea un token de `tokens.css`.

**Riesgos:** decidir la paleta final es una decisión de dirección de arte, no solo técnica; si no hay quien apruebe la paleta reconciliada, el sprint se retrasa. Mitigación: proponer una única opción bien fundamentada en el propio Brand Book en vez de presentar variantes a elegir.

---

### Sprint F2-2 — Librería de componentes reutilizables (6 días · A)

**Objetivo:** PLP, PDP, carrito y checkout comparten los mismos partials visuales; dejar de "verse como productos distintos".

**Dependencias:** Sprint F2-1 (los componentes deben nacer ya usando tokens).

**Tareas:**
- Extraer partials de Django (`{% include %}`) para: tarjeta de producto, precio (con y sin rango), swatch de color, selector de talla, badge, botón CTA, fila de confianza (trust row), galería de medios.
- Reescribir `producto_list.html`, `producto_detail.html`, `cart_detail.html` y `checkout.html` para consumir estos partials en vez de HTML propio.
- Extraer a un módulo JS pequeño y reutilizable la lógica de selección de variante que hoy vive solo dentro de `producto_detail.html` (para que un futuro drawer de carrito o una vista rápida en PLP puedan reutilizarla).

**Base de datos:** ninguna.

**Tests:** regresión de toda la suite existente (los 265 tests deben seguir en verde: los partials no deben cambiar ningún comportamiento, solo estructura). Añadir tests que verifiquen que el HTML resultante sigue conteniendo los mismos elementos funcionales (`variant_id`, botones de talla, etc.).

**Criterios de aceptación:** ningún fragmento de HTML de tarjeta/precio/badge está duplicado textualmente entre dos plantillas.

**Riesgos:** refactor amplio sobre pantallas ya probadas; alto riesgo de romper algo sutil. Mitigación: hacerlo *después* de tener toda la suite en verde (ya lo está) y ejecutar la suite completa tras cada partial extraído, no al final.

---

## Bloque B — Home y navegación (product-first)

### Sprint F2-3 — Home comercial pública y navegación persistente (6 días · A)

**Objetivo:** el primer viewport de Home muestra producto o categoría, no un formulario de acceso; existe una navegación persistente por audiencia/actividad.

**Dependencias:** Sprint F2-1, F2-2. Depende también de la **decisión de negocio #1** (§7): si el login obligatorio de Store se mantiene, los CTA "Comprar Mujer/Hombre" llevan a login con `?next=` hacia la categoría; si se flexibiliza, llevan directo a la PLP filtrada.

**Tareas backend:**
- Mapear las categorías reales (`Sport Premium`, `Conjuntos`, `Semi Personalizada`, `Alta costura personalizada exclusiva`) a las etiquetas de navegación del manuscrito (Novedades, Mujer, Hombre, Alta Costura, Tecnología). Donde no exista una categoría real equivalente (p. ej. "Mujer"/"Hombre" no son categorías hoy, son implícitas en la descripción del producto), documentar el gap de taxonomía como tarea de catálogo, no inventar una categoría vacía.
- Simplificar `gotogym/views.py::home` para dejar de calcular nada relacionado con el modal de influencer (ya inerte desde v2) y en su lugar pasar productos destacados (`featured=True`) para el hero/carrusel.

**Tareas frontend:**
- Rediseñar `home.html`: hero con foto de prenda/persona (usar imágenes reales de producto como fallback si no hay fotografía de campaña nueva — ver decisión de negocio #2), CTAs "Comprar Mujer", "Comprar Hombre", "Personalizar mi prenda"; login/registro pasan al ícono de cuenta en la navegación.
- Añadir navegación persistente en `base.html` (o un nuevo bloque de navegación específico de comercio) con los enlaces mapeados.
- Orden de módulos bajo el hero: novedades/destacados, categorías, alta costura, prueba social real (sin inventar reseñas), enlace a Journal/Blog.
- Rediseñar `logged_home.html` en la misma línea: bienvenida breve, accesos directos a Store/Mis pedidos/Blog como navegación real, no como enlaces sueltos; el orbe Quantum pasa a ser un elemento ambiental (10-15% del protagonismo, según Anexo A), no la pantalla completa.

**Base de datos:** ninguna nueva (usa `Product.featured` ya existente).

**Tests:**
- Regresión: login/registro siguen accesibles (desde el ícono de cuenta).
- Nuevo: la Home pública responde 200 sin sesión y contiene al menos un enlace a la PLP o a una categoría en el primer bloque de contenido.
- Nuevo: la navegación persistente aparece en Home, PLP y PDP con los mismos enlaces (consistencia).

**Criterios de aceptación:** un visitante anónimo ve una llamada a la acción de compra (no solo login/registro) en el primer viewport de la Home pública.

**Riesgos:** es el sprint con más tensión de decisión de negocio de toda la Fase 2 (ver §7 decisión #1). Mitigación: construir el CTA de forma que funcione correctamente en ambos escenarios (con o sin login obligatorio) para no bloquear el sprint mientras se confirma la decisión.

---

## Bloque C — PLP y PDP premium

### Sprint F2-4 — PLP visual competitivo (6 días · M)

**Objetivo:** la PLP deja de ser "un grid correcto" y se convierte en un catálogo competitivo con badges, chips y búsqueda real.

**Dependencias:** Sprint F2-2 (componentes), F2-3 (navegación ya coherente).

**Tareas backend:**
- Añadir `created_at` a `Product` (migración aditiva) para poder calcular "Nuevo" (p. ej. últimos 30 días) sin inventar un campo manual.
- Definir "Best seller" con un criterio real y verificable: conteo de `OrderItem` confirmados por producto en los últimos N días (no un campo manual arbitrario), reutilizando datos que ya existen desde v2 Sprint 8.
- Endpoint ligero de sugerencias de búsqueda (JSON, mismo dominio) para autocompletar por nombre de producto.

**Tareas frontend:**
- Badges "Nuevo"/"Best seller"/"Personalizable" (este último para la categoría de Alta Costura) sobre las tarjetas, usando el partial de badge del Sprint F2-2.
- Chips de filtros activos con botón de limpiar individual, además del "Limpiar" general que ya existe.
- Campo de búsqueda con sugerencias vivas (JS + el endpoint nuevo).

**Base de datos:** migración aditiva de `created_at` en `Product`.

**Tests:**
- Unit: "Nuevo" se calcula correctamente por fecha; "Best seller" por conteo real de ventas confirmadas.
- Unit: sugerencias de búsqueda no exponen productos inactivos o de otro estado.
- Regresión: los filtros existentes (talla/color/categoría/precio) siguen funcionando igual.

**Criterios de aceptación:** ningún badge se calcula a mano; todos salen de datos reales verificables.

**Riesgos:** bajo/medio.

---

### Sprint F2-5 — PDP premium: narrativa y confianza (6 días · A)

**Objetivo:** la ficha de producto deja de sentirse plana; incorpora la narrativa, la guía de decisión y la confianza que pide el manuscrito, en la medida de lo que el contenido real permita.

**Dependencias:** Sprint F2-2 (componentes, especialmente `MediaGallery` y `TrustRow`).

**Tareas backend:**
- Añadir campos de contenido a `Product` (o a una tabla relacionada, para no sobrecargar el modelo): `story` (por qué fue creada), `materials_technology`, `care_instructions`, `fit_notes` — todos opcionales, con `blank=True`, para no bloquear productos existentes sin ese contenido.
- Panel de administración (extender `administracion/forms.py::ProductAdminForm`) para editar estos campos nuevos.

**Tareas frontend:**
- Sección de narrativa bajo el bloque de compra: "Por qué fue creada", materiales/tecnología (separando explícitamente lo medido de lenguaje de marca, según §10.3 del manuscrito), cuidado, guía de talla/fit — cada una condicionada a que el campo tenga contenido (si está vacío, la sección no se muestra; nunca texto de relleno inventado).
- Trust row junto al CTA de "Añadir al carrito": tiempo de entrega estimado (reutilizando `shipping.services.get_mock_quote_estimate`, ya construido en v2) y enlace directo a la política de cambios (ya existe desde v2 Sprint 14).
- Galería con soporte visual para hasta 6+ medios cuando existan (el componente ya debe soportarlo desde F2-2); documentar explícitamente que el contenido fotográfico real es una tarea de negocio pendiente (decisión #2, §7), no de este sprint.

**Base de datos:** migración aditiva de los campos de contenido narrativo.

**Tests:**
- Unit: una sección de narrativa vacía no se renderiza (nunca contenido de relleno).
- Regresión: el flujo de selección de variante y "Añadir al carrito" no cambia.

**Criterios de aceptación:** un producto con contenido narrativo completo muestra las cuatro secciones; uno sin contenido no muestra ninguna sección vacía ni rota.

**Riesgos:** sin fotografía nueva, la mejora percibida será menor a la prometida por el manuscrito — se documenta explícitamente, no se oculta.

---

## Bloque D — Motion, carrito, accesibilidad y rendimiento reales

### Sprint F2-6 — Carrito como drawer + microinteracciones dirigidas por presupuesto de movimiento (6 días · A)

**Objetivo:** añadir al carrito no saca al usuario del catálogo; existe feedback inmediato y localizado en cada acción, sin violar la regla de "una animación dominante por pantalla".

**Dependencias:** Sprint F2-2 (componentes de carrito ya extraídos a partials).

**Tareas backend:** ninguna nueva (el servicio de carrito ya calcula todo correctamente desde v2); posible endpoint JSON ligero para renderizar el contenido del drawer sin recargar página completa.

**Tareas frontend:**
- Convertir el carrito en un panel lateral (drawer) en escritorio y pantalla completa/bottom-sheet en móvil, accesible desde el ícono de carrito en cualquier pantalla.
- Confirmación localizada de "Añadir al carrito" (el botón cambia de estado brevemente, el drawer se abre automáticamente) en vez de redirigir a una página nueva.
- Microinteracciones puntuales: crossfade corto al cambiar de color en PDP, microescala ×1.02 al seleccionar talla.
- Auditar que solo hay una animación dominante por pantalla (regla de "motion budget"); todo lo demás es microfeedback.
- Verificar que `prefers-reduced-motion` cubre las animaciones nuevas.

**Base de datos:** ninguna.

**Tests:**
- Regresión: todos los tests de `carrito` (agregar/quitar/actualizar, límites de stock) siguen pasando igual — el drawer es una capa de presentación, no cambia la lógica de servidor.
- Nuevo: el endpoint del drawer (si se crea) respeta login y disponibilidad exactamente igual que las vistas actuales.

**Criterios de aceptación:** agregar un producto al carrito desde la PDP no navega a otra URL; el usuario ve el carrito actualizado sin perder el contexto de la página en la que estaba.

**Riesgos:** medio — es el cambio de interacción más grande de la fase; requiere pruebas manuales exhaustivas en móvil.

---

### Sprint F2-7 — Accesibilidad y rendimiento con herramientas reales (6 días · A)

**Objetivo:** pasar de un checklist manual a datos verificables de accesibilidad y Core Web Vitals.

**Dependencias:** Bloques B y C completos (auditar sobre las pantallas ya rediseñadas, no antes).

**Tareas:**
- Ejecutar una auditoría automatizada real (axe-core o Lighthouse) contra un entorno con navegador disponible (staging o una máquina de desarrollo con Chrome/Chromium) — si el entorno de ejecución de este proyecto sigue sin navegador disponible, este es un **bloqueante técnico explícito** que debe resolverse antes de este sprint, no durante.
- Prueba manual de navegación 100% por teclado en el flujo completo Home → PLP → PDP → Carrito → Checkout.
- Pipeline de imágenes responsive: generar variantes de tamaño y formato WebP desde cada `ProductMedia.image` subida (usando Pillow, ya instalado), y servir `srcset` en las plantillas.
- Medir Core Web Vitals reales (LCP, INP, CLS) contra un entorno desplegado, documentando la línea base actual antes de optimizar.

**Base de datos:** ninguna (el pipeline de imágenes puede generarse en tiempo de subida o mediante un comando de gestión que procese lo existente).

**Tests:**
- Automatizados donde el entorno lo permita (axe-core contra las páginas principales).
- Manual, documentado explícitamente donde no sea automatizable.

**Criterios de aceptación:** existe un reporte con datos reales de accesibilidad y de Web Vitals, no solo un checklist de intenciones.

**Riesgos:** alto — depende de tener acceso a un navegador real, que hoy no está confirmado en el entorno de ejecución de este proyecto.

---

## Bloque E — Funcionalidades diferenciadoras

### Sprint F2-8 — Instrumentación de analítica de funnel (6 días · M)

**Objetivo:** cada paso del recorrido de compra deja un evento medible; existe una base para el programa experimental A/B que ambos manuscritos piden.

**Dependencias:** Bloques B, C y D completos (para que los eventos midan la experiencia final, no la intermedia).

**Tareas:**
- Modelo `AnalyticsEvent` (o integración con GA4 si hay measurement ID de negocio) con el esquema mínimo del manuscrito: `view_home`, `select_category`, `view_item_list`, `select_item`, `view_item`, `select_variant`, `add_to_cart`, `view_cart`, `begin_checkout`, `add_shipping_info`, `payment_redirect`, `purchase`.
- Cada evento incluye `product_id`/`variant_id` cuando aplique, moneda y valor; sin datos sensibles innecesarios.
- Reporte de guardrails: tasa de error, LCP/INP/CLS (reutilizando lo medido en F2-7), tasa de aprobación de pago (ya hay datos reales desde `PaymentTransaction`).
- Documentar (no necesariamente ejecutar) el diseño de los experimentos H1-H7 de la tabla del manuscrito, con hipótesis, variantes y métrica primaria.

**Base de datos:** migración de `AnalyticsEvent` si se opta por la capa propia.

**Tests:**
- Unit: cada evento se registra con los campos mínimos requeridos.
- Unit: los eventos no contienen PII innecesaria (nombre completo, dirección) — solo identificadores.

**Criterios de aceptación:** el recorrido completo Home→compra deja un rastro de eventos reconstruible.

**Riesgos:** bajo/medio.

---

### Sprint F2-9 — Wishlist y refuerzo de cuenta (6 días · M)

**Objetivo:** el cliente puede guardar productos e intención de compra sin perderla; se resuelve (o se documenta como rechazada) la decisión de guest checkout.

**Dependencias:** decisión de negocio #1 (§7) debe estar resuelta antes de este sprint.

**Tareas:**
- Modelo `Wishlist(user, variant)` simple; botón de guardar en PLP y PDP (usando el componente de CTA ya existente).
- Si el negocio confirma guest checkout: adaptar `create_order_from_cart` (ya diseñado en v2 con `user` nullable, según lo documentado en el propio roadmap v2 §14) para aceptarlo sin rediseño estructural. Si el negocio lo rechaza: este bloque de tareas se sustituye por libreta de direcciones guardadas en la cuenta del cliente.

**Base de datos:** migración de `Wishlist`; migración de guest checkout solo si aplica.

**Tests:**
- Unit: un usuario no ve la wishlist de otro (mismo patrón de aislamiento que `Order`).
- Unit (si aplica guest checkout): un pedido de invitado se crea correctamente, sin usuario, y es reclamable si el invitado se registra después con el mismo correo (alcance mínimo, sin sobre-diseñar).

**Criterios de aceptación:** depende de la decisión de negocio; documentado explícitamente cuál de las dos ramas se ejecutó y por qué.

**Riesgos:** este sprint no debe iniciarse sin la decisión de negocio ya tomada, para no construir en una dirección equivocada.

---

### Sprint F2-10 — Alta Costura como journey guiado (6 días · A)

**Objetivo:** la personalización deja de comportarse como "una categoría más" y se convierte en un flujo de cuatro pasos con progreso visible y precio transparente.

**Dependencias:** decisión de negocio #4 (§7) sobre el nivel de previsualización.

**Tareas backend:**
- Modelo `PersonalizationRequest` (usuario, producto base, selecciones por paso, estado, precio/abono, timestamps).
- Servicio que calcule precio y tiempo estimado según las selecciones, sin sorpresas al final.
- Al confirmar, crear una `Order` marcada con un estado o nota que indique "requiere producción a medida" (reutilizando `Order.internal_note`, ya existente desde v2 Sprint 11).

**Tareas frontend:**
- Flujo de cuatro pasos (Uso → Fit → Diseño → Confirmación) con barra de progreso, guardable y reversible.
- Previsualización según el nivel decidido en §7 (ilustración por combinación como mínimo defendible, no necesariamente 3D).
- Resumen final: especificaciones, precio total/abono, tiempo estimado, siguiente acción.

**Base de datos:** migración de `PersonalizationRequest`.

**Tests:**
- Unit: el precio final coincide exactamente con la suma de las selecciones (una sola fuente de verdad, igual que el resto del checkout).
- Integration: el flujo completo genera una `Order` reconciliable con el resto del panel de administración de pedidos (ya construido en v2 Sprint 12).

**Criterios de aceptación:** un producto de la categoría "Alta costura personalizada exclusiva" ya no se compra con el mismo flujo que un producto estándar.

**Riesgos:** alto — es el sprint más nuevo conceptualmente de toda la Fase 2, sin nada equivalente construido en v2 sobre lo cual apoyarse.

---

### Sprint F2-11 — Reseñas verificadas y activación condicional de Mercado Pago (6 días · M)

**Objetivo:** cerrar los dos últimos pendientes de ambos manuscritos que dependen de que exista suficiente historial de compra real o de credenciales externas.

**Dependencias:** Sprint F2-8 (para poder medir el impacto), decisión de negocio #3 (credenciales de Mercado Pago).

**Tareas:**
- Modelo `Review` con FK a `OrderItem` (para `verified_purchase` real, no simulada) — el prerequisito (`OrderItem`) ya existe desde v2 Sprint 8.
- Si hay credenciales de sandbox reales: activar `PAYMENT_PROVIDER=mercadopago` en un entorno de prueba y validar el flujo de punta a punta contra el sandbox real (la arquitectura ya está lista desde v2 Sprint 18; esto es activación, no construcción).
- Conectar `crm/hubspot_config.py` a los eventos de `AnalyticsEvent`/`Order` para automatizar, como mínimo, notificación de abandono de carrito y confirmación de compra.

**Base de datos:** migración de `Review`.

**Tests:**
- Unit: solo un usuario con `OrderItem` confirmado de esa variante puede dejar una reseña verificada.
- Integration (si hay credenciales): flujo de pago real contra sandbox de Mercado Pago.

**Criterios de aceptación:** las reseñas mostradas en PDP (si las hay) son 100% de compras verificadas; nunca simuladas.

**Riesgos:** la parte de Mercado Pago depende enteramente de que el negocio provea credenciales; si no llegan, el sprint entrega solo reseñas y CRM, documentando la activación de pagos como pendiente (igual que se hizo honestamente en v2 Sprint 18).

---

# 10. Matriz de trazabilidad

| Requisito | Fuente | Sprint | Estado de partida |
|---|---|---|---|
| Sistema de tokens único | Dirección de Diseño §11 | F2-1 | No existe (dos sistemas de color) |
| Componentes reutilizables | Dirección de Diseño §11 | F2-2 | No existe |
| Home product-first | Ambos manuscritos, hallazgo P0 | F2-3 | No resuelto (fuera de alcance de v2) |
| Navegación persistente | Rediseño Competitivo §8.1 | F2-3 | No existe |
| Badges/chips/búsqueda en PLP | Rediseño Competitivo §8.2 | F2-4 | Parcial |
| Narrativa y trust row en PDP | Dirección de Diseño §7.3, Anexo A | F2-5 | No existe |
| Carrito como drawer | Dirección de Diseño §7.5 | F2-6 | No existe (página completa) |
| Motion / game feel | Dirección de Diseño §8 | F2-6 | Mínimo |
| Accesibilidad con herramienta real | Dirección de Diseño §11, Anexo A | F2-7 | Manual únicamente |
| Rendimiento medido | Dirección de Diseño Anexo A | F2-7 | Sin medir |
| Analítica de funnel | Dirección de Diseño §13 | F2-8 | No existe |
| Wishlist / guest checkout | Rediseño Competitivo §9; decisión de negocio | F2-9 | No existe |
| Alta Costura guiada | Dirección de Diseño §7.4 | F2-10 | No existe |
| Reseñas verificadas / Mercado Pago real | Ambos manuscritos; v2 §14 | F2-11 | Prerequisitos listos, no activado |

---

# 11. Estimación total

| Rango | Valor |
|---|---|
| Número de sprints | 11 (F2-1 a F2-11) |
| Duración por sprint | 6 días (el doble que los sprints de v2, de 3 días) |
| Días estimados | 66 días hábiles |
| Semanas estimadas (1 persona, jornada completa) | ≈ 13.2 semanas |
| Sprints de complejidad **alta** | F2-2, F2-3, F2-5, F2-6, F2-7, F2-10 — 6 de 11 |
| Mayor incertidumbre | F2-3 (depende de decisión de negocio sobre login) y F2-7 (depende de acceso a navegador real para medir) |

---

# 12. Orden recomendado de ejecución

```
Bloque A — Fundamentos (no negociable empezar aquí)
  F2-1  Sistema de tokens de diseño unificado
  F2-2  Librería de componentes reutilizables

Bloque B — Home y navegación
  F2-3  Home comercial pública y navegación persistente

Bloque C — PLP y PDP premium
  F2-4  PLP visual competitivo
  F2-5  PDP premium: narrativa y confianza

Bloque D — Motion, carrito, accesibilidad, rendimiento
  F2-6  Carrito como drawer + microinteracciones
  F2-7  Accesibilidad y rendimiento con herramientas reales

Bloque E — Funcionalidades diferenciadoras
  F2-8  Instrumentación de analítica de funnel
  F2-9  Wishlist y refuerzo de cuenta (o guest checkout, según decisión de negocio)
  F2-10 Alta Costura como journey guiado
  F2-11 Reseñas verificadas y activación condicional de Mercado Pago
```

Antes de iniciar F2-1, se necesita resolver o al menos poner fecha a las cinco decisiones de negocio de la sección 7 — ninguna bloquea el arranque del Bloque A, pero la #1 bloquea materialmente el diseño correcto de F2-3, y la #2 determina cuánto de la promesa de F2-5 es alcanzable con contenido real.
