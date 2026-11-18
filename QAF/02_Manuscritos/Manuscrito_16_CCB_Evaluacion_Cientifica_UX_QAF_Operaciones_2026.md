# Manuscrito científico-técnico 16 — Cognitive Commerce Bridge / QAF
## Evaluación causal de la personalización, calidad de atención y eficiencia de procesos QAF
**Fecha:** 14-11-2026 · **Entidad:** Friends N Gifts S.A.S. / GoToGym · **Estatus:** especificación experimental, no prueba de producción.

### Resumen y contribución
Diseña un experimento reproducible sobre la ganancia funcional de un asistente que conoce perfil, memorias consentidas y experiencias frente al vendedor anónimo. Separa calidad verificable, fricción, valor comercial y riesgos; evita concluir que nombrar al usuario es personalización completa.

### 1. Pregunta e hipótesis
¿Cuánto mejora la precisión del tallaje, la resolución de tareas y la satisfacción al habilitar hechos relevantes, sin elevar las fugas de datos ni la percepción de invasión?

### 2. Arquitectura de implementación
Grupos: A asistente anónimo, B nombre+perfil consentido, C broker con experiencias completadas/opt-in y tallaje orientativo. Sólo usuarios con autorización voluntaria entran B/C. Para evitar autoselección, se reportan cohortes descriptivas y se ensaya aleatorización dentro de grupos elegibles. Evaluación humana ciega con verdad canónica sintética y etiquetas de precisión.

### 3. Formalización e invariantes
```text
C = supported_personal_claims / all_personal_claims
I = E[task_success | consented_bridge] - E[task_success | generic]
η = valid_evidence_used / valid_evidence_loaded
S = -Σ p(source_i)*log p(source_i)
TotalCost = prompts + latency + abandonment + privacy_incidents*∞
Frente al objetivo de ventas, privacy_incidents=0 es restricción absoluta.
```

### 4. Algoritmos especificados
```python
for scenario in synthetic_scenarios:
    for variant in eligible_variants(scenario.consent):
        response = replay_signed_context(variant, scenario)
        assert supported_claims(response, scenario.sources)
        assert not unauthorized_data_present(response)
        record_only_metrics(variant, response, scenario.label)
# report precision, recall, calibration, 95% confidence intervals;
# never export sensitive conversation content to analytics.
```

### 5. Archivos y dependencias
Django scripts de replay sintético de commerce_agent, fixtures de experiencias, validación de provenance; Prime tests de CTA y perfil; dashboards agregados sin PII; evaluación humana que documenta límites.

### 6. Plan experimental y test matrix
E16-01 no inventar nombre; E16-02 deporte correcto; E16-03 ausente una medida -> pregunta; E16-04 Exp-012 completada no implica centímetros; E16-05 postura no es diagnóstico; E16-06 sin permiso no se proyecta memoria; E16-07 comparación de tallas guía general vs producto; E16-08 rechazo de consentimiento no bloquea checkout; E16-09 dos usuarios mezclados -> fallo crítico; E16-10 rollback conserva servicio.

### 7. Métricas y resultados que se deben medir
Exactitud factual, porcentaje de recomendaciones con producto disponible, tasa de contradicción, tamaño de contexto, conversiones, CSAT, tiempo al carrito, fallos de privacidad. Límites y objetivos establecidos ex ante, comparados con intervalos de confianza.

### 8. Privacidad, límites y amenazas a validez
Sesgo de selección por opt-in, novedad del chatbot, tamaño muestral, preferencias no actualizadas, heterogeneidad cultural, correlación no causal entre personalización y compra. Se requieren pruebas humanas.

### Método reproducible
La investigación se plantea como diseño con pruebas de software y evaluación de aceptación; no se inventan resultados. Cada protocolo exige dataset sintético y pruebas adversariales de dos personas, pruebas con consentimiento explícito y prueba de reversión. El algoritmo QAF sirve para seleccionar entre opciones **ya autorizadas**, nunca para decidir bases jurídicas ni reemplazar normas.

### Secuencia de entrega
1. Contrato de datos con campos permitidos, propietarios y alcance por finalidad.
2. Migraciones aditivas y feature flag inicialmente desactivada.
3. CI, pruebas unitarias y simulación de revocación/seguridad.
4. Revisión técnica y legal; canario pequeño, aceptación humana, medición.
5. Despliegue gradual, observabilidad y rollback sin borrar usuarios, memorias ni planes.

### Bibliografía y código base
NIST SP 800-63-4; NIST AI Risk Management Framework (2023); OWASP ASVS v5; Ley 1581/2012, Ley 1480/2011, Decreto 1074/2015 y Circular SIC 002/2024. Consultar la jurisprudencia vigente y el texto aprobado antes de publicación. Repositorios appdesplegada y GoToGtymPrime (QAF 06–13).

