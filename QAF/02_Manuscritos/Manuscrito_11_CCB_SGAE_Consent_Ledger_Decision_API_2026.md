# Manuscrito científico-técnico 11 — Cognitive Commerce Bridge / QAF
## Sistema de decisiones de autorización, ledger por eventos y Decision API interoperable
**Fecha:** 14 noviembre 2026 · **Autor institucional:** GoToGym, Friends N Gifts S.A.S. · **Estado:** propuesta técnica, funciones validadas solo cuando su PR y pruebas lo acrediten.

### Resumen
Se propone un registro de eventos de autorización y revocación que permite reutilizar decisiones por finalidad demostrablemente equivalente entre APP Django y Prime, sin confundir identidad, aceptación contractual y acceso a memorias personales. La innovación técnica propuesta es una política determinista de prueba mínima, con idempotencia transaccional y revocación monotónica, estudiada mediante experimentos falsables.

### 1. Problema de ingeniería y evidencia de código
Los permisos comerciales actuales residen en CommercePersonalizationConsent de Prime y Django interpreta una aserción firmada por turno. No existe una Decision API transaccional central que permita consultar pruebas jurídicas interoperables, criterios de equivalencia de versión ni revocación universal. La activación de un flag no sirve como prueba.

### 2. Hipótesis falsable
Un ledger append-only de decisiones por propósito reduce solicitudes repetidas en usuarios con permisos equivalentes, sin aumentar concesiones incorrectas ni filtraciones frente al baseline con consentimientos independientes.

### 3. Marco formal, variables e invariantes
```text
DecisionEvent = (event_id, issuer, subject_ref, purpose, data_category, product_scope,
notice_hash, notice_version, allowed, captured_at, expires_at,
revoked_at, evidence_ref, sequence, idempotency_key)

Permit(u,p,d,product,t) = IdentityVerified(u)
  AND ProofExists(u,p,d,product) AND ProofAllowed(u,p,d,product)
  AND PurposeEquivalent(p, product) AND VersionApproved(notice_hash)
  AND NOT Revoked(u,p,d,t) AND NOT Expired(u,p,d,t)

Si no se conoce la prueba o equivalencia, Permit = false.
RevocationSeq(u,p,d) >= GrantSeq(u,p,d) => no lectura (fail closed).
El consentimiento publicitario nunca se identifica como permiso de perfil comercial.
```

### 4. Arquitectura e integración entre repositorios
**Django**: nuevas tablas ConsentDecisionEvent y PolicyNoticeVersion (migración aditiva); adaptador de identidad `issuer+oid`; service de decisión transaccional de solo lectura + POST del usuario autenticado con CSRF; endpoints administrativos con acceso restringido; mecanismo de revocación y invalidación de continuidad. **Prime**: adaptador tipado que lee snapshot firmado o consulta API interna protegida, conserva scopes de CommercePersonalizationConsent como fallback; nadie crea un evento por coincidencia de email. **Prueba de origen**: el documento legal aprobado se almacena como hash SHA-256; sin aprobación se conserva modo genérico. Idempotency key por evento; revocaciones con sequence monotónico, 2PC no requerido si el consumidor falla cerrado.

### 5. Algoritmos de referencia
```python
def authorize(request, proof, approved_notice, now):
    principal = resolve_oidc_issuer_oid(request)
    if principal is None:
        return "LINK_REQUIRED"
    if approved_notice is None or approved_notice.status != "approved":
        return "POLICY_NOT_PUBLISHED"
    if not proof or not proof.matches(principal, approved_notice):
        return "OPT_IN_REQUIRED"
    if proof.revoked_at or proof.expires_at <= now:
        return "OPT_IN_REQUIRED"
    return "ALLOW_MINIMUM_CONTEXT"

def revoke_atomic(tx, principal, purpose, seq):
    tx.lock(principal, purpose)
    if seq <= tx.last_sequence: return "STALE_EVENT_REJECTED"
    tx.append_event(allowed=False, sequence=seq)
    tx.invalidate_context_epoch(principal, purpose)
    return "REVOKED"
```

### 6. Mapa de cambios implementables
Backend/appdesplegada: `backend/api/commerce_agent/identity.py`, nuevo `backend/api/consent_ledger/models.py`, `service.py`, `policy.py`, `urls.py`; Prime: `gotogym/vendedor/consentimiento.py`, nuevo `consent_sync.py`, `personalizacion.py`. La librería pura actual `scripts/qaf_legal_decision_engine.py` es prototipo, no reemplaza endpoints autenticados.

### 7. Protocolo de pruebas y aceptación
L11-01 identidad ambigua: denegar; L11-02 consentimiento explícito válido: permitir; L11-03 misma finalidad y versión ya autorizada: no repreguntar; L11-04 finalidad distinta: pedir; L11-05 autorización expirada/revocada: denegar; L11-06 replay de evento: denegar; L11-07 escritura concurrente de grant/revoke: último sequence válido; L11-08 dos usuarios mismo correo: sin mezcla; L11-09 permiso de memoria personal APP: no implica permiso comercial; L11-10 caída API: atención general sigue funcionando.

### 8. Métricas científicas y umbrales de validación
Exactitud de autorizaciones = decisiones correctas / casos etiquetados. Error de concesión indebida objetivo 0; revocación efectiva antes del siguiente turno; latencia P95 del cálculo determinista y porcentaje de pantallas evitadas, sin convertir optimización en fundamento jurídico.

### 9. Amenazas a validez, seguridad y privacidad
Invalidez de una autorización migrada; sincronización eventual tardía; documentos legales aún no aprobados; respaldo con eventos antiguos. Requiere abogado colombiano, análisis de transmisiones y finalidades, gestión de titulares y revisión de seguridad antes de producción.

### 10. Pasos de entrega, rollback y no-objetivos
1. Preparar branch, test unitario y migraciones aditivas si aplican.
2. Validar que el usuario de prueba conserva perfil, plan, historial y vínculo OIDC.
3. Ejecutar tests de denegación por defecto, dos usuarios y revocación.
4. Integrar después de revisión de políticas y QA, desplegar en canario, y comprobar logs seguros.
5. Mantener flag de rollback y atención anónima general sin borrar datos.
**No objetivo:** acceso del Shop a toda la memoria clínica o empresarial de un cliente; inferir consentimiento del login; sustituir al responsable legal por la IA.

### Protocolo científico y trazabilidad
Se trata de un manuscrito científico-técnico de **diseño e implementación reproducible**, no de evidencia de eficacia clínica, legal o comercial demostrada. Las hipótesis anteriores deben falsarse mediante datos de prueba sintéticos, y validarse en canario con cuentas existentes verificadas y consentimiento activo. Los experimentos deben registrar versión de código, hash de políticas, pruebas CI, p95, número de datos proyectados, fallos y motivos sin registrar conversaciones o secretos.

### Referencias y antecedentes
- QAF Manuscritos 06 (identidad), 07 (broker), 08 (continuidad), 09 (jurídico) y 10 (BPMN/SGAE), en `QAF/02_Manuscritos`.
- ISO/IEC 27001 y OWASP ASVS 5.0 como marcos de controles; NIST AI RMF 1.0, https://www.nist.gov/itl/ai-risk-management-framework
- NIST SP 800-63-4 para identidad: https://pages.nist.gov/800-63-4/
- Código: `gotogymsaas/GoToGtymPrime` y `gotogymsaas/appdesplegada`, archivos indicados en cada capítulo.
- Ley 1581 de 2012, Decreto 1074 de 2015, SIC Circular Externa 002 de 2024. La autoridad jurídica se decide con la versión vigente y asesoría colombiana.

