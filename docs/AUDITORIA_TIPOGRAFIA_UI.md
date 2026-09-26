# Auditoría visual y de UI/UX: sistema tipográfico

> Documento temporal de trabajo. Recoge el diagnóstico y la propuesta de
> sistema tipográfico/visual para GoToGym, basado en evidencia extraída
> directamente del CSS en producción (no en impresión visual). Ningún
> cambio de código se aplicó todavía — este documento es la base para
> decidir el orden de implementación.

## A. Diagnóstico

### La percepción inicial, contrastada con evidencia

No es que algunos títulos estén "mal calibrados" de forma aislada — el
problema real es más sistémico: **el mismo rol semántico (título de
héroe, título editorial) tiene definiciones de tamaño distintas y
contradictorias según el archivo CSS que lo maneje.** Eso es objetivo,
verificable, y es la causa de que la inconsistencia se perciba sin poder
señalar un culpable único.

### Hallazgos objetivos (verificados en el CSS real)

**1. La misma clase, tres tamaños distintos.** `.editorial-title` está
definida tres veces con escalas de `clamp()` diferentes:
- `editorial_pages.css`: `clamp(3rem, 7vw, 7rem)` → hasta **112px**
- `editorial_pages.css` (otra regla, más abajo): `clamp(1.9rem, 4.2vw, 3.6rem)` → hasta **58px**
- `commerce_editorial.css`: `clamp(2.5rem, 6vw, 5.2rem)` → hasta **83px**

Según la página, "el título editorial" mide entre 58px y 112px en desktop.

**2. Colisión de selectores por etiqueta, no por clase.** `store_home.css`
define `h1` dos veces con reglas que se pisan: `clamp(3.45rem, 7.2vw, 7rem)`
vs. `clamp(3.2rem, 15vw, 5rem)` (tasa de crecimiento casi el doble de
agresiva). Lo mismo con `h2`: `clamp(2.25rem, 5vw, 4.7rem)` vs.
`clamp(3.2rem, 7vw, 7rem)`. Cuál gana depende del orden de carga y la
especificidad, no de una decisión de diseño.

**3. Existe un sistema de tokens de tamaño… que nadie usa.** `style.css`
ya define una escala completa (`--font-size-xs` a `--font-size-3xl`, de
12px a 56px). Búsqueda en las 9 hojas de estilo del proyecto: **cero usos
reales.** Cada tamaño en pantalla es un valor suelto, no una referencia a
esa escala — el mismo patrón (abandonado) que existía con el espaciado
antes de tokenizarlo.

**4. Micro-tamaños casi duplicados sin razón funcional.** Para
eyebrow/etiqueta/meta-texto hay **siete** tamaños distintos entre 9.7px y
11.5px: `.61rem, .64rem, .65rem, .68rem, .7rem, .72rem, .74rem`. Ningún
ojo humano distingue 10.4px de 10.9px.

**5. El acento itálico editorial usa una fuente del sistema, no de marca.**
El texto en cursiva dorada ("*forma de avanzar*", "*la persona*", "*próximo
movimiento*") usa:
```css
.editorial-title em { font-family: Georgia, serif; }
```
`Georgia` es una fuente del sistema operativo. Mientras tanto, **Playfair
Display (peso 700) está descargada y empaquetada en `static/fonts/` sin
usarse en ningún template.** El elemento tipográfico más reconocible de la
marca depende hoy de qué fuente serif traiga instalado el sistema
operativo de cada visitante.

**6. Pesos de fuente sin archivo real detrás.** Solo hay dos pesos reales
cargados de TT Norms (400 y 800) y uno de Outfit (400) — Outfit 700 está
en disco sin usar, mismo patrón que Playfair. El CSS pide `font-weight:
500` (10 veces), `600` (9 veces) y `700` (22 veces) sobre esa familia:
ninguno tiene archivo real, el navegador sintetiza un "falso negrita" de
calidad y consistencia variables por navegador.

**7. Unidades mezcladas.** La mayoría en `rem` (correcto, respeta zoom del
usuario), pero `.gtg-nav-links` está en `13px` fijo.

### Lo que NO está objetivamente mal

- `line-height` (1.1–1.2 en titulares, 1.5–1.7 en cuerpo) sigue la
  práctica estándar.
- `letter-spacing` (negativo en titulares grandes, positivo en etiquetas
  uppercase) también es correcto — solo falta tokenizar.
- El texto de cuerpo (15.2px–17.3px según contexto) varía pero dentro de
  un rango razonable.
- El sistema de espaciado (`--space-1` a `--space-9`) está bien construido
  y cada vez más adoptado — es la referencia a seguir, no tocar.

---

## B. Principios de diseño propuestos

1. **Un rol, un tamaño.** Cada nivel jerárquico (héroe, título de sección,
   subtítulo, cuerpo, etiqueta) tiene una sola definición de tamaño, peso
   y line-height — nunca una por archivo.
2. **Los tokens existentes se completan, no se reinventan.** La misma
   disciplina que ya funciona en espaciado se aplica a tipografía.
3. **Cero pesos sintéticos.** Si un peso no tiene archivo de fuente real
   cargado, no se usa — o se carga el archivo que falta.
4. **La fuente editorial de marca se usa donde ya se diseñó para usarse.**
   Playfair Display deja de ser un archivo muerto.
5. **Escala modular, no aritmética.** Los tamaños de título crecen por una
   proporción constante entre niveles, no por números redondeados sin
   relación entre sí.
6. **Fluido con techo y piso explícitos.** Un solo conjunto de curvas
   `clamp()` reutilizado, no una por archivo.

---

## C. Sistema tipográfico recomendado

Escala en base **1.25 (major third)**, con `clamp()` de mínimo (móvil) y
máximo (desktop ancho) explícitos:

| Token | Móvil (mín) | Desktop (máx) | `clamp()` | Peso | Line-height | Uso |
|---|---|---|---|---|---|---|
| `--text-display` | 40px | 96px | `clamp(2.5rem, 5vw + 1rem, 6rem)` | 800 | 1.05 | Héroe de Home únicamente (1 por página) |
| `--text-h1` | 32px | 56px | `clamp(2rem, 3vw + 1.2rem, 3.5rem)` | 800 | 1.1 | Título de página (PLP, PDP, Journal listado, Acerca de, Contacto) |
| `--text-h2` | 26px | 40px | `clamp(1.625rem, 2vw + 1.1rem, 2.5rem)` | 700 | 1.15 | Título de sección dentro de una página |
| `--text-h3` | 20px | 26px | `clamp(1.25rem, .8vw + 1rem, 1.625rem)` | 700 | 1.25 | Subtítulo / nombre de producto en PDP |
| `--text-lead` | 16px | 19px | `clamp(1rem, .3vw + .9rem, 1.1875rem)` | 400 | 1.6 | Bajada de héroe / intro de sección |
| `--text-body` | 15px | 16px | `clamp(.9375rem, .1vw + .9rem, 1rem)` | 400 | 1.6 | Párrafo estándar |
| `--text-small` | 13px | 14px | `clamp(.8125rem, .05vw + .8rem, .875rem)` | 500–600 | 1.5 | Meta-datos, precio secundario, SKU |
| `--text-label` | 11px | 11px | `11px` fijo | 700–800 | 1.2 | Eyebrow, badge, nav, botón — `uppercase` + tracking |

Reemplaza los 8 tamaños de héroe/título en conflicto por 4 niveles reales,
y las 7 micro-variantes de etiqueta por 1.

**Pesos:** usar solo 400 (texto), 700 (énfasis, subtítulos) y 800 (héroe,
h1, nav, botones) — los tres que ya existen como archivo real. Retirar
500/600 de la familia display/body, o cargar esos pesos si de verdad se
necesita un peldaño intermedio (no se recomienda: con 400/700/800 alcanza).

**Tracking:** negativo en display/h1/h2 (`-0.02em` a `-0.04em`, ya usado,
solo se tokeniza), positivo en label/nav/botón (`0.08em`, ya usado).

---

## D. Sistema visual complementario

| Categoría | Recomendación |
|---|---|
| **Espaciado** | Ya resuelto (`--space-1`…`--space-9`, base 4px). No tocar, solo terminar de adoptar donde aún queden valores sueltos. |
| **Border-radius** | Consolidar en 3 tokens: `--radius-sm: 8px` (chips, inputs), `--radius-md: 12px` (tarjetas), `--radius-pill: 999px` (botones/badges). Hoy hay 3 formas distintas de escribir "pill" (`999px`, `9999px`, el token) — unificar a una. |
| **Shadows** | Un solo `--shadow-card` para toda superficie elevada (existe, infrautilizado — 45 sombras sueltas vs. pocas con el token). Un segundo `--shadow-quantum` para el efecto de "campo", más difuso y con tinte de acento en vez de negro puro. |
| **Colores** | Ya tokenizados razonablemente — no hay fragmentación comparable a la tipográfica, fuera del alcance de esta auditoría. |
| **Bordes/divisores** | `1px solid rgba(248,249,250,.12–.16)` repetido con opacidades distintas (.12, .16, .18, .25) para el mismo "divisor sutil". Consolidar en `--border-subtle`. |

---

## E. Adaptación Quantum + Editorial

El equilibrio no se logra agregando efectos — se logra dejando que cada
mitad del concepto ocupe el rol donde ya es fuerte:

- **Editorial gobierna la tipografía y la composición**: la jerarquía de
  la sección C, el uso real de Playfair Display para el acento itálico,
  márgenes generosos, mucho blanco/negro en reposo. Ya está en la
  dirección correcta — el activo (Playfair) solo falta conectarlo.
- **Quantum gobierna el movimiento y la superficie, nunca el texto**: las
  animaciones de superposición/colapso (G1) y las franjas de interferencia
  (G3+G4) ya implementadas son el lugar correcto para la física cuántica —
  no debe tocar tamaño ni peso de un titular. Un titular no "colapsa"
  tipográficamente; un selector de producto sí.
- **Toque Quantum en superficies**: `--shadow-quantum` (difuso, tinte
  turquesa/dorado al 8–12% en vez de negro) en tarjetas destacadas y en el
  estado `:focus` de inputs — un halo, no un cambio de forma.
- **Microinteracción con justificación, no decoración**: reutilizar el
  mecanismo de `pdp-collapse` (G1) para cualquier cambio de texto en vivo
  en vez de inventar uno nuevo por sección.
- **Nada de gradientes/transparencias nuevas en texto** — dañan
  legibilidad y no hay razón de marca para introducirlos ahora.

---

## F. Plan de implementación

Orden por impacto/riesgo, no por facilidad:

1. **Conectar Playfair Display** (falta el `<link>`) — cambio de una
   línea, impacto visual inmediato y coherente en 6+ páginas de una vez.
2. **Reemplazar los tokens de tamaño muertos por los de la sección C**, en
   `style.css` donde ya viven los actuales `--font-size-*`.
3. **Migrar `.editorial-title`, los `h1`/`h2` de héroe, y
   `.shop-pdp__title`** a los nuevos tokens — resuelve las 3 definiciones
   contradictorias de un solo golpe porque pasan a ser la misma variable
   en los tres archivos.
4. **Retirar `font-weight: 500/600`** de la familia display/body en favor
   de 400/700/800 real.
5. **Consolidar las 7 micro-variantes de eyebrow/label** en
   `--text-label`.
6. Recién ahí, **radius/shadow/border** (impacto menor, cosmético).

---

## G. Criterios de validación

1. **Grep de cero, no ojo.** `grep -c "var(--text-" static/css/*.css` debe
   subir de 0 a un número alto; `grep -c "font-size: [0-9.]*rem"` (valores
   sueltos) debe bajar a casi cero fuera de `tokens.css`.
2. **Ninguna clase con dos definiciones.** `.editorial-title`, `h1`, `h2`
   aparecen una sola vez como bloque de reglas de tamaño en todo el
   proyecto (o con overrides explícitos por breakpoint, nunca por
   archivo).
3. **Cero pesos sintéticos.** DevTools → Computed → Rendered Fonts en un
   titular debe mostrar el archivo real cargado, no "synthetic bold".
4. **Captura A/B por página** — Home, PLP, PDP, Journal, Acerca de,
   Contacto, Carrito, Checkout, Login — para confirmar que el mismo rol se
   ve igual en las ocho, no solo en la que motivó la revisión.
5. **Prueba en tres anchos** (móvil ~375px, tablet ~768px, desktop
   ~1440px) verificando que ningún `clamp()` produce un salto brusco entre
   mínimo y máximo.
6. **El criterio de éxito es consistencia inter-página, no una preferencia
   de tamaño** — si el diagnóstico lleva a agrandar en vez de achicar algo,
   eso también cuenta como éxito.

---

## Pendiente de confirmar antes de tocar código

No falta nada para ejecutar C, D y F — todo sale del CSS real. Lo único
que no se puede verificar sin el dueño del proyecto: si `Georgia` fue una
decisión consciente en algún momento (por ejemplo, para evitar el peso de
descarga de Playfair). Si es así, reconsiderar el punto 1 del plan antes
de aplicarlo.
