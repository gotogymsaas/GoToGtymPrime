# Manuscrito científico-técnico 15 — Cognitive Commerce Bridge / QAF
## Seguridad Zero Trust, observabilidad y políticas como código para el puente cognitivo
**Fecha:** 14-11-2026 · **Entidad:** Friends N Gifts S.A.S. / GoToGym · **Estatus:** especificación experimental, no prueba de producción.

### Resumen y contribución
Implementa un plan de amenazas verificable para proteger credenciales HMAC, OIDC, pruebas de consentimiento, lecturas de memoria y acciones comerciales. Propone un sistema de gates automáticos para detectar drift del contrato, pruebas de roles y uso indebido de herramientas antes de producción.

### 1. Pregunta e hipótesis
¿Cómo demostrar que una credencial de servicio, un prompt malicioso o una identidad ajena no permiten consultar información privada bajo COMMERCE_LINKED?

### 2. Arquitectura de implementación
Dos capas de firma separadas, Azure Key Vault con identidad administrada, no guardar valores literales ni tokens. Replay con jti consumido en caché atómica. Django `ai_role_isolation.py` prohíbe lectura personal directa; solo Context Broker proyecta hechos consentidos. Prime sanea acciones propuestas y valida stock/precios en servidor. CI SAST, test de migración, policy-as-code de documentos, control de egress LLM, alertas y playbooks.

### 3. Formalización e invariantes
```text
Authorization = ValidServiceSignature AND ValidOIDCAssersion
  AND NonReplay AND OwnerMatch AND ActiveScopes AND AllowlistedField
LeastPrivilegeConstraint: AllowedTools(COMMERCE_LINKED) ∩
  {personal.read, business.read, admin.read, health.read} = ∅
AdversarialLeakRate = leaked_sensitive_cases / attack_cases
```

### 4. Algoritmos especificados
```python
def secure_turn(service_packet, identity_assertion, prompt):
    require_valid_service_hmac(service_packet)
    identity = verify_and_consume_identity(identity_assertion)
    role = COMMERCE_LINKED if identity else COMMERCE
    facts = commercial_policy_project(identity, prompt) if identity else []
    assert not contains_forbidden_keys(facts)
    model = narrate(catalog_evidence, facts)
    return sanitize_proposals_and_claims(model, catalog_evidence)
```

### 5. Archivos y dependencias
Prime `vendedor/{firma,contrato,respuesta,identidad}.py`, GitHub workflow CI; Django `commerce_agent/{signing,identity,context_broker,turn,actions}.py` y `superagent/ai_role_isolation.py`. QAF Cybersecurity se incorpora como observador, no como autoridad de consentimiento.

### 6. Plan experimental y test matrix
S15-01 firma servicio inválida 401; S15-02 firma identidad inválida -> anónimo; S15-03 replay jti -> rechazo; S15-04 prompt injection en catálogo -> no ejecutar; S15-05 payload con medidas crudas -> rechazo por contrato; S15-06 cross-user A/B -> 0 filtraciones; S15-07 secreto KV sin resolver -> no firmar; S15-08 versión documental drift -> alerta; S15-09 perfiles Business/Admin fuera de Commerce; S15-10 acciones de carrito no se ejecutan sin confirmación.

### 7. Métricas y resultados que se deben medir
Cobertura de ataque por clase, falsos positivos de control, incidentes de autorización, logs sin PII, latencia de HMAC/broker y disponibilidad de atención anónima durante fallas.

### 8. Privacidad, límites y amenazas a validez
Degradación de Redis, drift en Key Vault, prompt injection indirecta, API externa accesible por público, error de configuración; planes de rollback y verificación activa. No confiar en un único test verde.

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

