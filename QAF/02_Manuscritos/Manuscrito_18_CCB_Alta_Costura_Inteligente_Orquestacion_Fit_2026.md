# Manuscrito científico-técnico 18 — Cognitive Commerce Bridge
## Alta Costura Inteligente: evidencias de talla, mediciones voluntarias y personalización textil verificable

**GoToGym / Friends N Gifts S.A.S. | 14-11-2026 | Investigación de ingeniería textil y UX, no certificación de tallaje.**

### Resumen
Se estudia cómo maximizar una atención que use deporte y preferencias verificadas, memoria comercial consentida, orientación antropométrica real y la experiencia educativa Alta Costura Inteligente de la APP. Se propone una arquitectura por niveles de evidencia que evite afirmar tallas a partir de fotos 2D, peso, estatura, silueta o postura. El siguiente paso ideal del cliente es contextualmente el mínimo: confirmar talla habitual, registrar medida con cinta, usar la guía real del producto o consultar a un profesional de confección.

### 1. Evidencia del código real
Prime contiene \`TailoringMeasurement\` (pecho, cintura, cadera y entrepierna, máximo 180 días de vigencia), \`vendedor/talla.py\` que compara contra guía general y \`vendedor/paquete.py\` que envía solo \`size_hint\` sin centímetros si \`tailoring.measurements\` está activo. La APP contiene Exp012 Shape/Presence y Exp013 Posture/Proportion, basadas en keypoints y resultados proxy, no antropometría real. ISO 8559-1:2017, confirmada como vigente en 2026, establece definiciones y métodos de toma de medidas para tallaje de ropa.

### 2. Pregunta e hipótesis
¿La distinción visible entre medidas confirmadas, guía general y ausencia de evidencia reduce las recomendaciones de talla injustificadas? H1: sí, frente a un vendedor que presume talla con peso/altura o salta a una talla M por una compra anterior. H2: la oferta voluntaria de experiencias 2D mejora el entendimiento de la silueta, pero no se convierte en una medida de confección real. Ambas exigen verificación humana.

### 3. Jerarquía de evidencia
\`\`\`text
E0 = sin medidas; pedir preferencia o medida voluntaria
E1 = talla habitual declarada; orientación, confirmar marca/ajuste
E2 = medida manual reciente + guía general; orientación sin garantía
E3 = medida manual validada + tabla de DIMENSIONES DEL PRODUCTO; mejor ajuste estimado
E4 = toma de medidas por especialista + patrón textil; confección individual a confirmar
PX = postura / silueta 2D = evidencia educativa, NO E2/E3/E4
\`\`\`
El sistema **no** debe pasar de PX a una circunferencia en cm. Debe etiquetar y validar vigencia de medidas (máximo 180 días según implementación Prime), completitud, contradicciones dimensionales y preferencia de fit. La recomendación debe incluir su fuente.

### 4. Modelo de ajuste textil
\`\`\`text
if not user_consented(tailoring.measurements): return unknown
if stale(measures, days=180): return ask_to_refresh
if product_chart is missing:
    return general_guide_orientation(measures), certainty="reference_only"
d(s, product) = Σ_(dimension measured) w_dimension *
              |body_dimension - garment_target(s, product)| / tolerance_dimension
return argmin_s d(s, product) ONLY if all required dimensions are available;
otherwise: abstain / ask_missing_dimension / human_fitting.
\`\`\`
Los pesos, tolerancias y tablas se deben validar por diseño de prenda, tela, elasticidad y prueba física; no hay calibración experimental demostrada. El consentimiento de una persona no se hereda de otra aunque ambas compartan apellido o correo.

### 5. Orquestador de experiencia
1. El comprador dice «quiero una camiseta para jugar tenis».
2. El Coach usa deporte favorito y preferencias permitidas, muestra prendas y disponibilidad reales.
3. Si pregunta talla, comprueba si existe evidencia: talla guardada/medidas vigentes/guía de prenda.
4. Cuando faltan medidas, muestra una instrucción breve y no invasiva de cinta métrica o acceso a Mi cuenta. El usuario puede comprar sin hacerla.
5. Si el usuario manifiesta interés por silueta o postura, propone abrir la APP para Exp012/Exp013, respetando permiso independiente de completitud.
6. Si desea alta costura individual, ofrece intervención humana y una propuesta formal de confección; no inventa servicio disponible ni promete ajuste sin especificaciones.
7. La compra y la propuesta de confección nunca equivalen a un diagnóstico médico.

### 6. Cambio tecnológico previsto
Fase A, funcional sin nuevos datos: permitir \`open_solution coach_app\`, consentimientos separados, reconocimiento de completitud y respuesta honesta. Fase B, nueva tabla de dimensiones por prenda + versión del patrón + tabla con rango/correspondencia y tolerancias. Fase C, servicio de fit con explicación, incertidumbre y una preferencia de ajuste. Fase D, diseño/alteraciones personalizadas sujetas a cotización humana. Se necesitan PRs independientes en catálogo y pruebas de producto; no basta con el documento.

### 7. Pruebas adversariales
X18.01 M declarada no equivale a talla universal; X18.02 sólo peso/altura: abstención; X18.03 producto sin tabla: citar guía general; X18.04 con medidas recientes y guía específica: orientación reproducible; X18.05 medidas de >180 días: actualización; X18.06 pecho/cadera incompatibles: preguntar ajuste; X18.07 Exp012 completada: no extraer cm; X18.08 usuario rechaza permiso: checkout libre; X18.09 cambiar de usuario: no heredar medidas; X18.10 inventario no vigente: no ofertar; X18.11 permisos de salud nunca usados por comercio; X18.12 cotización a medida exige confirmación humana.

### 8. Evaluación y metas
Error de talla respecto a fitting presencial, tasa de cambios/devoluciones por talla, éxito de una compra con usuario informado, número de preguntas repetidas, confianza declarada, conversiones sin dark patterns, latencia p95, fugas 0. Se compararán cohortes representativas y se reportarán intervalos de incertidumbre antes de afirmar precisión.

### 9. Riesgos y límites
Variabilidad de talla entre prendas, lavado, elasticidad, patrón, sesgo de auto-medición y fotos 2D. La alta costura inteligente es una experiencia de servicio, no una promesa de talla infalible. Proteger medidas y no deducir género, condición médica o atractivo.

### 10. Bibliografía
ISO 8559-1:2017 https://www.iso.org/standard/61686.html ; MediaPipe https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker ; código Prime \`vendedor/talla.py\`, \`models.py\`, \`paquete.py\`, Django \`qaf_shape_presence/engine.py\` y \`qaf_posture_proportion/engine.py\`; QAF manuscritos 06–17.
