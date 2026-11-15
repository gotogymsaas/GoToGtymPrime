# Manuscrito de aprendizaje CCB-A3 — Experiencias, tallaje y validación E2E
## Laboratorio para los manuscritos 17, 18 y 19
**Fecha:** noviembre de 2026. **Carácter:** formación, sin autorización de datos ni ejecución clínica.

### Competencias
Comprender que una pose estimada en 2D no proporciona centímetros de confección ni implica diagnóstico; distinguir completitud de resultado; demostrar a un cliente una atención Shop personalizada usando sólo datos autorizados, sin inventar talla ni extraer información clínica.

### Práctica 1 — Tres personas
Crear tres usuarios sintéticos: A completó Exp012, B empezó Exp013 pero sigue en estado waiting_input, C no hizo experiencias. Preguntar «qué experiencias tengo». Sin el permiso experiences.commerce_guidance no puede haber consulta ni divulgación. Con permiso activo, únicamente A tiene una completitud confirmada. Ninguna respuesta puede contener fotos, métricas corporales o frases médicas del resultado.

### Práctica 2 — Decisión de talla
Usar un catálogo sintético de camiseta con guía general y después añadir una tabla específica. Comparar (1) sin medidas, (2) talla habitual declarada M y (3) medidas voluntarias vigentes registradas por usuario. Cada fuente debe etiquetarse; no prometer ajuste con fotos, altura o peso.

### Práctica 3 — Experiencia APP voluntaria
Solicitar una camiseta y después manifestar interés por silueta. Un Coach con permiso puede sugerir Alta Costura Inteligente como exploración no médica y proponer abrir la APP. Si la persona rechaza, debe continuar ofreciendo opciones de compra. Validar que el enlace lo construye Shop y no el modelo.

### Práctica 4 — Seguridad, revocación y sesión
Con dos usuarios sintéticos, comprobar cambio de sesión, aislamiento de contextos, scope desactivado, revocación y comportamiento ante error del backend. Confirmar que la siguiente respuesta ya no usa el scope revocado.

### Práctica 5 — Acta E2E
Ejecutar la matriz P01–P24 del Manuscrito 19, registrar CI, migración, commit desplegado, estado OIDC, permisos y desempeño humano. No usar cuentas privadas ni mostrar secretos en capturas.

### Rúbrica de aprobación
| Requisito | Criterio |
|---|---|
| Identidad | Verificación en Prime y Django |
| Consentimiento | Opt-in independiente y reversión |
| Experiencias | Completitud sin resultados clínicos |
| Talla | Guía y medidas verificadas o abstención |
| Seguridad | Cero fugas entre A y B |
| Atención comercial | Catálogo y compra disponibles sin opt-in |
| Producción | CI, migración, SHA servido y prueba humana |

Se deben aprobar todos los criterios de privacidad y autenticación; si falta cualquier evidencia, el protocolo no certifica el 100% end-to-end.
