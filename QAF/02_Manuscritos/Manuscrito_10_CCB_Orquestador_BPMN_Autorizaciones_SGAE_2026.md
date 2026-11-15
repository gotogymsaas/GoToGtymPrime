# Manuscrito científico-técnico 10 — Automatización de procesos y gobierno jurídico interoperable
## SGAE Orchestrator: BPMN, motor de decisión, eventos verificables y flujos GoToGym APP ↔ Prime

**GoToGym QAF / Friends N Gifts S.A.S.** · 14 de noviembre de 2026 · Diseño de ingeniería, versión 1.0 · Revisión jurídica pendiente.

### Resumen
Se especifica un sistema de automatización empresarial que reduce la fricción repetitiva entre Quantum Coach (APP) y Shop (Prime) mediante identidad federada, autorización verificable por finalidad, registro de decisiones y orquestación de experiencias. El sistema no asume que la aceptación de T&C habilite usos secundarios de datos. Diferencia decisiones contractuales obligatorias de autorizaciones opcionales y permisos sensibles. El análisis del código actual encuentra términos divergentes en ambos productos y consentimiento granular ya implementado en Prime; se propone integrar una capa decisional mínima y reversible, de manera que el cliente no repita autorizaciones **equivalentes y demostrables**, pero tampoco se interpreten consentimientos por silencio.

### 1. Alcance y sistemas
- **APP Django / appdesplegada:** autoridad de perfil de bienestar, identidades verificadas, motor de proyección de datos (Cognitive Commerce Bridge), control de acceso a memorias.
- **Prime / GoToGtymPrime:** UX comercial, catálogo, compra, medidas confirmadas y autorización de personalización Shop.
- **Entra External ID:** autenticación, no autorización contractual ni permiso para consultar la memoria privada.
- **SGAE:** registro de decisiones documentadas, motor de equivalencia de finalidad y coordinador de procesos.
- **Servicios externos:** pagos, correo, marketing y dispositivos fuera del alcance del primer release. No se conceden autorizaciones por inferencia.

### 2. Modelo formal de negocio
Sea k el par (issuer, oid) resuelto de forma segura; p la finalidad; d la categoría de datos; a el anexo contractual; v la versión de aviso; t el momento. Se reutiliza una decisión cuando:

~~~text
Reuse(k,p,d,a,v,t) =
  IdentityVerified(k)
  AND EvidenceExists(k,p,d)
  AND Allowed(k,p,d)
  AND NotRevoked(k,p,d,t)
  AND NotExpired(k,p,d,t)
  AND EquivalentPurpose(p,d,a,v)
  AND LegalBasisReviewed(p,d,a,v)
~~~

La equivalencia jurídica es una **tabla aprobada y versionada**, no una medida de similitud semántica ni la elección de un LLM. La regla \`Reuse=0\` no impide atención comercial general.

### 3. Estados y transiciones BPMN
Estados: \`ANONYMOUS\`, \`AUTHENTICATED_UNLINKED\`, \`LINKED_NO_CONTRACT\`, \`LINKED_NO_OPTIONAL_CONSENT\`, \`LINKED_BASIC_CONTEXT\`, \`LINKED_TAILORING_CONTEXT\`, \`REVOKED\`, \`LEGAL_POLICY_UPDATE_PENDING\`.

~~~mermaid
flowchart TD
  Start[Visitante] --> Login{Sesión Entra válida?}
  Login -->|No| Generic[Chat y catálogo general]
  Login -->|Sí| Link{Vínculo Prime/Django verificable?}
  Link -->|No| LinkStep[Vinculación con prueba de posesión]
  Link -->|Sí| Contract{Anexo contractual aplicable aceptado?}
  Contract -->|No| ContractStep[Leer y aceptar anexo pertinente]
  Contract -->|Sí| Perm{¿Finalidad comercial opcional?}
  Perm -->|No| Ready[Continuar operación]
  Perm -->|Sí| Proof{¿Existe prueba vigente equivalente?}
  Proof -->|Sí| Bridge[Broker de datos autorizados]
  Proof -->|No| Ask[Consulta contextual opt-in]
  Ask -->|Autoriza| Bridge
  Ask -->|Rechaza| Generic
  Bridge --> Shop[Recomendación, talla y compra]
  Generic --> Shop
~~~

### 4. Modelo de dominio y contratos
**DocumentRegistry:** \`document_code, product_scope, locale, version, sha256, effective_from, effective_to, approved_by, approval_ref, publication_status\`.
**AuthorizationDecisionEvent:** \`event_id, resolved_principal, purpose_code, data_category, product_scope, allowed, notice_code, notice_version, captured_at, expires_at, revoked_at, evidence_ref, idempotency_key\`.
**ConsentProjection:** \`principal_ref, purpose, allowed, validated_at, version, validity_reason\`, sin exponer memoria personal.
**LegalFlowState:** \`principal_epoch, contract_required, optional_prompt_required, ready_for_commerce, reason_code\`.

Contratos de API propuestos, *no publicados*:
- \`GET /internal/sgae/decisions?purpose=<code>\` solo identidad de servicio y persona vinculada; datos mínimos.
- \`POST /internal/sgae/decisions\` con idempotency key, autenticación y autorización de usuario con prueba de acción.
- \`POST /internal/sgae/revocations\` append-only y prioridad de invalidación.
- \`GET /api/sgae/experience-state\` interfaz reducida sin PII para el cliente autenticado.
La base de datos Django se considera fuente jurídica de autoridad **solo tras aprobación y elección de dueño de datos**, no por esta propuesta. Mientras tanto Prime mantiene \`CommercePersonalizationConsent\` y su auditoría; no migrar masivamente.

### 5. Algoritmo de autorización conservador
En ambos repositorios se implementa una librería pura \`scripts/qaf_legal_decision_engine.py\` como primer prototipo verificable: compara finalidad, producto y versión de aviso, expiración y revocación; devuelve estados sin leer bases ni modificar permisos. El prototipo **no es todavía la Decision API**. Debe evolucionar a un servicio autenticado y transaccional después de revisión legal.

Requisitos para el servicio:
- verificaciones \`issuer + oid\` en ambos servicios;
- prueba de aceptación por versión; no aceptar correo como identidad;
- las decisiones de datos sensibles se mantienen en ámbitos especializados;
- consistencia eventual con eventos, revocaciones con prioridad y invalidación de caché;
- rechazo de eventos duplicados, replay y escrituras concurrentes;
- separación de acceso de comprador, administrador y operador de privacidad;
- conservación de evidencias conforme a políticas legales aprobadas;
- interacción con narrador LLM **únicamente** tras comprobación determinista.

### 6. Reglas de automatización
| Evento | Regla | Acción |
|---|---|---|
| Login exitoso | k verificado | Consultar estado de contrato y finalidades |
| Login local sin enlace | Sin k válido | Ofrecer vinculación; atención general no se bloquea |
| Contrato vigente y aceptado | Versión y alcance coinciden | Omitir pantalla redundante |
| Contrato nuevo esencial | Falta aceptación | Presentar nueva versión para la operación pertinente |
| Finalidad comercial opcional | Prueba ausente | Mostrar aviso contextual, una sola decisión |
| Consentimiento activo equivalente | Prueba vigente | Construir proyección permitida |
| Consentimiento denegado | No permitido | Ofrecer experiencia genérica y compra |
| Revocación | Evento con actor verificado | Invalidar contexto al turno siguiente |
| Cambio de usuario / logout | Nueva época | Rotar historial y no reutilizar decisiones ajenas |
| Falta de documento aprobado | \`publication_status=pending\` | Bloquear auto-publicación de nuevo texto |
| Nueva ley/sentencia | Alerta de drift | Abrir tarea de revisión humana; no modificar términos silenciosamente |

### 7. Cumplimiento automático y alcance legal
El auditor inicial \`scripts/qaf_legal_policy_audit.py\` produce SHA-256 de fuentes legales, verifica inventario, valores de opt-in por defecto y detecta la referencia antigua de reembolso a 30 días en Prime. Usa \`config/qaf_legal/governance_manifest.json\`. No sustituye evaluación normativa ni evidencia real de autorización. El workflow \`.github/workflows/qaf-legal-governance.yml\` ejecuta auditoría y tests de reglas deterministas. Publicar términos requiere firma de abogado/función de privacidad y revisión de versión, no un merge automático.

**Actualización jurídica de noviembre de 2026:** la Sentencia C-192 de 2026 de la Corte Constitucional aclaró el alcance uniforme del plazo de quince días calendario por retracto para modalidades del artículo 47 de la Ley 1480. Fuente: https://www.corteconstitucional.gov.co/relatoria/2026/c-192-26.htm. Verificar condiciones legales de ejecución por operación; no anunciar reembolsos incondicionales.

### 8. Resiliencia, consistencia y datos personales
- **Fail closed:** sin prueba equivalente, no emitir proyección personalizada.
- **Fail operational:** el servicio general de catálogo/checkout sobrevive si falta una autorización opcional.
- **Event store:** no sobrescribir revocaciones con una réplica tardía; monotonicidad de sequence por actor/finalidad.
- **No mezcla:** token de servicio no confiere facultad para acceder a memorias de otras personas.
- **No contenido privado en logs:** eventos de razón, latencias, documentos/versiones y métricas agregadas.
- **No inferencia legal automatizada por IA:** el LLM puede explicar lenguaje claro, pero no conceder consentimientos ni redactar silenciosamente nuevos derechos.
- **Sin marketing implícito:** los mensajes operativos y de venta no significan autorización publicitaria general.

### 9. Plan de ingeniería y cambios por repositorio
**APP Django**
1. Modelo de eventos de decisión y documentos aprobados con migraciones aditivas.
2. Endpoints internos con autenticación fuerte, autorización por sujeto, CSRF cuando aplica, idempotencia y versionado.
3. Resolver equivalente de finalidad, revocación y invalidación en \`commerce_agent/context_broker.py\`.
4. Panel personal de autorizaciones y exportación de evidencia.
5. Auditoría por pruebas y telemetría sin PII.

**Prime**
1. Sustituir consultas locales repetidas por un \`ConsentDecisionAdapter\` cuando la Decision API esté validada.
2. Mantener fallback a \`CommercePersonalizationConsent\` únicamente donde exista prueba válida.
3. Cambiar onboarding a \`PolicyResolver\`, mostrar anexo contractual pertinente si falta y CTA de personalización solo cuando se necesite.
4. Conservar libre acceso a catálogo, soporte y checkout general cuando rechaza personalización.
5. Corregir y versionar términos, privacidad y retracto tras aprobación legal.

### 10. Experimentos de aceptación
| ID | Caso | Resultado obligatorio |
|---|---|---|
| P01 | Usuario con autorización vigente misma finalidad/version | No re-preguntar |
| P02 | Permiso de memoria personal APP, sin permiso Shop | No reutilizar |
| P03 | Persona rechaza personalización | Puede comprar y conversar |
| P04 | Consentimiento revocado en un canal | No proyectar en el siguiente turno |
| P05 | Cambio A→B en mismo navegador | Cero datos o pruebas cruzadas |
| P06 | Documento legal nuevo sin aprobación | No publicar |
| P07 | Contrato Shop no aceptado | Solicitar contrato esencial sin crear scopes opcionales |
| P08 | Consentimiento expirado | Solicitud contextual de nueva decisión |
| P09 | Datos de salud en memoria | No exportar al vendedor |
| P10 | Evidencia falsa o repetida | Rechazo + trazabilidad |
| P11 | Compra con talla sin medidas | Expresar incertidumbre, no inventar |
| P12 | Reembolso de retracto | Plazo y condiciones conforme a ley/sentencia |

### 11. Métricas QAF y criterios científicos
- \`C\` coherencia: % de acciones de UX congruentes con evidencia jurídica vigente.
- \`I\` impacto: mejora relativa (medida con control) en finalización de compra y atención útil.
- \`eta\` eficiencia: pasos legales redundantes evitados / pasos totales potenciales.
- \`S\` entropía descriptiva de estados del proceso; no representa fenómeno cuántico físico.

El éxito exige **cero falsas concesiones** y **cero fugas entre usuarios**, aun cuando la eficiencia comercial disminuya. Los parámetros y metas son hipótesis a medir con ensayos, no hechos probados.

### 12. Despliegue y aprobación
Release 0 (este manuscrito): auditor estático, manifiesto y motor puro con tests, sin conexión a datos reales. Release 1: documento aprobado, mapeo jurídico de propósitos, canario de Decision API. Release 2: automatización contextual de APP/Prime, consentimiento y revocación transaccional. Release 3: rollback probado, auditoría externa y test E2E con usuarios reales voluntarios. Ningún release modifica de forma retroactiva autorizaciones sin prueba.

### 13. Referencias
Manuscrito 09 de esta serie; QAF 06, 07 y 08; Ley 1581 de 2012, Decreto 1074 de 2015, Ley 1480 de 2011, Ley 2439 de 2024, Sentencia C-192 de 2026, Ley 527 de 1999 y SIC Circular 002 de 2024. Se recomienda revisar formalmente los contratos con encargados/proveedores antes del uso cruzado.