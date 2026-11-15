# Programa científico-técnico de implementación CCB / SGAE
**Producto:** GoToGym APP y Prime | **Ámbito:** automatización de procesos, protección de datos, atención comercial sin fricción | **Fecha:** 14-11-2026.

## Visión
Una identidad verificada, documentos jurídicos coherentes, autorizaciones válidas reutilizables por **finalidad equivalente**, y atención personalizada únicamente con datos permitidos. El acceso general, catálogo y compra no requieren permisos opcionales de perfil o memoria.

## Manuscritos y dependencias (en orden)
| ID | Manuscrito | Objetivo de implementación | Módulos principales | Gate de aprobación |
|---|---|---|---|---|
| 09 | Gobernanza jurídica y experiencia sin fricción | Marco contractual común y anexos, separación contrato/consentimiento, protección de datos y consumidor | APP términos/privacidad; Prime terms/privacy/politicas_contenido | Revisión jurídica colombiana |
| 10 | SGAE Orchestrator / BPMN | Estados de negocio, automatización de decisión, manifiestos, auditor y pruebas | \`scripts/qaf_legal_decision_engine.py\`, \`qaf_legal_policy_audit.py\`, \`config/qaf_legal/*\` | CI automatizado; no despliegue contractual |
| 11 | Event-Sourced Consent Ledger y Decision API | Prueba por versión/finalidad, idempotencia, revocación, equivalencia de políticas y API autenticada | Django modelo aditivo/servicio; Prime adapter | Tests de concurrencia y privacidad |
| 12 | Onboarding omnicanal BPMN y UX contextual | Login-vinculación-consentimiento-pago con mínima fricción; evita preguntas repetidas | Prime \`accounts/*\`, \`vendedor/personalizacion.py\`; APP onboarding/Perfil | A/B accesible; compra sin opt-in |
| 13 | Cognitive Commerce Context por finalidad | Contexto de perfil y memoria comercial exclusivamente autorizado; tallaje orientativo | Django \`commerce_agent/context_broker.py\` + evidence; Prime talla | Cero fugas de salud/Business/Admin |
| 14 | Derechos del titular, retención y revocación | Consulta de prueba, rectificación, borrado gobernado y revocación al turno siguiente | Django privacidad/memoria; Prime ConsentAudit | Legal/DPO + registros y backups |
| 15 | Seguridad, trazabilidad, cumplimiento continuo | Policy-as-code, SAST, detección drift legal, monitoreo y rollback | CI de ambos repos, observabilidad QAF | Ciberseguridad y pruebas adversariales |
| 16 | Evaluación experimental QAF y operaciones | Validación de eficiencia, comprensión, exactitud, satisfacción, conversión | Métricas anónimas, ensayos canario y pruebas humanas | Métricas, privacidad, acta aceptación |

## Reglas arquitectónicas no negociables
1. La identidad \`issuer + oid\` no equivale a autorización para un uso comercial de datos.
2. La memoria personal del Coach no se exporta por habilitar términos generales.
3. Las decisiones de consentimiento requieren evidencia consultable de texto, versión, finalidad, fecha, medio y titular verificado.
4. Una revocación invalida la lectura desde el turno siguiente, incluyendo caché y contexto conversacional.
5. Las decisiones desconocidas y no equivalentes deben mantenerse sin autorizar; no se convierten a \`true\` por migración.
6. Datos sensibles de salud/wearables, Business y Admin permanecen fuera del rol comercial por defecto.
7. Las versiones nuevas de términos y privacidad requieren revisión y aprobación humana antes de publicarse.
8. El servicio general y checkout siguen operando cuando se rechaza personalización.
9. Cada PR debe incluir pruebas, checklist de roll-back y verificación de negocio; nunca introducir nuevas cuentas o contraseñas.

## Implementación real de esta etapa
**Hecho en ramas de trabajo de APP y Prime:** manifiesto, auditor read-only, motor puro de decisión, pruebas unitarias y workflow GitHub Actions. **Hecho en documentación:** manuscritos 09 y 10.
**Aún no implementado:** Event Sourcing en PostgreSQL, API de decisiones, sincronización de consentimientos reales, UI contextual end-to-end, cambios contractuales efectivos, migración de decisiones existentes, publicación en producción.

## Entregables de aceptación del programa
- Flujo guest→login→compra sin permiso opcional y sin bloqueo.
- Para usuario con consentimientos vigentes y equivalentes, no se repiten decisiones y se prueba el origen.
- Para usuario sin consentimiento, hay opción real de rechazo y atención general.
- Cambio de cuenta, cambios de política, revocación, expiración y conflicto de identidad no filtran información.
- Términos, anexos y política de privacidad de APP y Shop coherentes, accesibles, versionados y aprobados.
- Reglas legales auditadas con la jurisprudencia colombiana vigente al momento de publicación.
- KPI experimentales: pasos repetidos, tiempo hasta primera recomendación útil, tasa de comprensión, tickets, revocación efectiva y errores de autorización, sin inventar resultados.
