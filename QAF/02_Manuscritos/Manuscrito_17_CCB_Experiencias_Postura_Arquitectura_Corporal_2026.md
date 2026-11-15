# Manuscrito científico-técnico 17 — Cognitive Commerce Bridge
## De las experiencias de postura y arquitectura corporal a una atención comercial educativa

**GoToGym / Friends N Gifts S.A.S. | 14-11-2026 | Investigación y especificación; no prueba clínica.**

### Resumen
Se diseña un puente de experiencias entre la APP de Quantum Coach y el Shop que recomiende tres capacidades existentes: Corrección de Postura (Exp-006), Alta Costura Inteligente (Exp-012) y Arquitectura Corporal (Exp-013). El objetivo es que el vendedor pueda orientar al usuario hacia la experiencia pertinente, reconocer si la completó (cuando lo autorice) y distinguir las limitaciones de los resultados; sin copiar imágenes, keypoints, puntuaciones físicas, medidas o diagnósticos al comercio.

### 1. Evidencia examinada
En appdesplegada el catálogo \`docs/MATRIZ_EXPERIENCIAS_CHAT.md\` registra Exp006, Exp012 y Exp013, con capturas guiadas, \`service_intent\` y persistencia en ExperienceTask. \`docs/POSTURE_ROLLOUT.md\`, \`POSTURE_PROPORTION_ROLLOUT.md\` y \`QAF/02_experimentos/exp-012__shape-presence-intelligence/README.md\` muestran estimaciones de pose basadas en puntos 2D, no antropometría en centímetros. \`docs/DIAGNOSTICO_PERSONALIZACION_QUANTUM_COACH_2026-10-24.md\` advierte limitaciones de personalización de Exp013. En Prime las medidas de confección las aporta el cliente voluntariamente bajo \`tailoring.measurements\`.

### 2. Hipótesis científica falsable
En consumidores con consentimiento, una sugerencia contextual y voluntaria de experiencias educativas pertinentes reducirá preguntas repetidas y aumentará la comprensión de las opciones de la APP, sin elevar afirmaciones erróneas sobre tallas o salud. Se requiere ensayo A/B; ningún resultado de mejora ha sido observado todavía.

### 3. Modelo formal
Sea q una pregunta comercial y E el catálogo de experiencias. Se propone:
\`\`\`text
Eligible(u,e,q) = VerifiedOIDC(u) AND Grant(u,"experiences.commerce_guidance")
                  AND e∈{Exp006,Exp012,Exp013} AND Relevant(q,e)
Completion(u,e) = EXISTS ExperienceTask(user=u, experience=e,
                                         status∈{"result_ready","completed"})
Projection = {public_label, optional_next_step, completion_status, limitations}
Forbidden = {photos, keypoints, clinical_scores, body_cm, private_results, health_profile}
\`\`\`
La selección QAF optimiza la relevancia únicamente después de filtrar la elegibilidad. Sin consentimiento, no se consulta ExperienceTask. Un registro \`waiting_input\` no significa experiencia completada.

### 4. Algoritmo reproducible
\`\`\`python
def commercial_guidance(verified_identity, question, shop_size_hint):
    if not verified_identity or "experiences.commerce_guidance" not in verified_identity.scopes:
        return []
    candidates = desired_experiences(question)
    if not candidates:
        return []
    completed = ExperienceTask.objects.filter(
        user_id=verified_identity.user_id, experience_id__in=candidates,
        status__in=("result_ready", "completed")
    ).values_list("experience_id", flat=True)
    return public_only_guidance(candidates, completed, shop_size_hint)
\`\`\`
La función de selección se implementa dentro de Django, nunca en el navegador. Prime mantiene el nuevo permiso separado y desactivado por defecto. El vendedor puede proponer una acción \`open_solution: coach_app\` cuyo URL valida el servidor Shop; no se envía un link arbitrario del modelo.

### 5. Selección y experiencia del usuario
- Pregunta por **talla o ajuste**: si no hay medidas confirmadas, ofrecer Alta Costura Inteligente como exploración opcional de silueta; aclarar que no mide centímetros ni garantiza talla.
- Pregunta por **proporciones o arquitectura**: ofrecer Arquitectura Corporal, útil como orientación no diagnóstica.
- Pregunta por **postura**: ofrecer Corrección de Postura como educación corporal, nunca como evaluación clínica ni inferencia de ajuste de una camiseta.
- Si el usuario ya completó una experiencia, el Coach conoce únicamente ese estado y ofrece continuar si corresponde; no presume resultados.
- Si no tiene permiso, atender normalmente y preguntar de forma no invasiva lo estrictamente necesario para la venta; nunca exigir experiencias para comprar.
- La entrada a la APP requiere identidad válida; no abrir captura automáticamente ni reutilizar imágenes del Shop.

### 6. Archivos concretos
Django: \`backend/api/commerce_agent/experience_guidance.py\`, \`context_broker.py\`, \`identity.py\`, \`knowledge_bridge.py\`, \`narration.py\` y \`turn.py\`. Prime: \`gotogym/vendedor/{models,personalizacion,consentimiento}.py\`, migración aditiva y botón de solución seguro. La implementación real está en PRs separados de documentación, con pruebas CI.

### 7. Pruebas de aceptación
X17.01 Sin scope: ninguna consulta a experiencias; X17.02 A completó Exp012 y B no: aislamiento; X17.03 \`result\` con fotos no sale a prompt; X17.04 waiting_input no equivale a completed; X17.05 pregunta por talla: consejo opcional y límites; X17.06 postura: no diagnóstico; X17.07 hola: no empujar experiencias; X17.08 revocación: próxima respuesta sin datos del scope; X17.09 consentimiento y memoria Business/Admin no se mezclan; X17.10 URL final a APP es de una solución permitida; X17.11 no discriminación por nombre, sexo o condición corporal; X17.12 prueba humana móvil y accesibilidad.

### 8. Métricas y QAF
C: exactitud de afirmaciones sobre completitud de experiencias. I: utilidad incremental declarada y resolución real de la compra. η: proporción de hechos necesarios usados sin repetir preguntas. S: incertidumbre de fuentes. Metas de seguridad: fugas 0, resultados sensibles compartidos 0, afirmaciones de cm derivadas de 2D 0. No se atribuye ventaja cuántica.

### 9. Limitaciones y ética
Las cámaras y los puntos 2D pueden producir proxies dependientes de iluminación, posición, ropa y algoritmo; no sustituyen una medición antropométrica estandarizada. La experiencia de postura no diagnostica lesión. Evitar juicios estéticos, presión comercial, perfilamiento no solicitado y uso de resultados de menores. Ejecutar pilotos sólo con voluntarios informados.

### 10. Referencias
Google MediaPipe Pose Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker ; ISO 8559-1:2017 confirmada en 2026: https://www.iso.org/standard/61686.html ; código APP y Prime citado en el apartado 6; NIST AI RMF 1.0: https://www.nist.gov/itl/ai-risk-management-framework.
