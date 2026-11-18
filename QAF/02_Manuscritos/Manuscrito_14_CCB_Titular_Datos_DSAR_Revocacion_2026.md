# Manuscrito científico-técnico 14 — Cognitive Commerce Bridge / QAF
## Derechos del titular, revocación, minimización y gobierno de retención omnicanal
**Fecha:** 14-11-2026 · **Entidad:** Friends N Gifts S.A.S. / GoToGym · **Estatus:** especificación experimental, no prueba de producción.

### Resumen y contribución
Diseña procesos comprobables de consulta, corrección, exportación, revocación y supresión entre APP y Prime, respetando retenciones exigidas por ley y eliminando la memoria comercial cuando procede. La ingeniería se fundamenta en control de propietario e historial de eventos, no en decisiones discrecionales del LLM.

### 1. Pregunta e hipótesis
¿Puede un titular retirar el permiso de uso comercial de una preferencia y comprobar su efecto en la siguiente respuesta sin borrar innecesariamente historial contractual o de pagos?

### 2. Arquitectura de implementación
Django administra solicitudes DSAR autorizadas por el usuario; Prime valida el mismo titular y acepta revocación local inmediata. Un servicio de reconciliación detecta eventos desfasados sin aplicar grants retroactivos. Datos de medidas se borran conforme a la política de Prime y respaldo técnico; un registro mínimo de auditoría permanece cuando existe obligación legal. La memoria empresarial/admin queda fuera del flujo del vendedor.

### 3. Formalización e invariantes
```text
State(u,p,t) = latest_valid_event(u,p,t) en {ALLOWED, REVOKED, EXPIRED}
ReadAllowed = IdentityVerified AND State=ALLOWED AND PurposeEquivalent
PrivacyDebt = (#read_after_revocation) + (#unexplained_retentions)
Invariant: PrivacyDebt=0 para toda sesión del corpus controlado.
```

### 4. Algoritmos especificados
```python
def revoke(principal, purpose, token):
    require_verified_subject(principal)
    event = append_revocation_with_idempotency(principal, purpose, token)
    invalidate_commerce_context_epoch(principal, purpose)
    delete_purpose_exclusive_data_if_applicable(principal, purpose)
    return {"status": "revoked", "receipt": event.public_receipt}

def data_access_request(principal, requested_categories):
    require_session_and_reauth_if_sensitive(principal)
    return minimized_personal_export_by_owned_scope(requested_categories)
```

### 5. Archivos y dependencias
Django: consentimiento, DRF/views privadas, ledger, tarea programada de reconciliación, auditoría. Prime: `vendedor/consentimiento.py`, `models.py`, `personalizacion.py`, métricas; contrato de sincronización revocación prioritaria.

### 6. Plan experimental y test matrix
R14-01 revocar perfil y repetir pregunta, 0 hechos; R14-02 revocar medidas destruye TailoringMeasurement; R14-03 revocación en APP y Shop convergen; R14-04 consulta no permite referencia a otro actor; R14-05 pagos se retienen por obligación aplicable sin exportarse al vendedor; R14-06 backup restore no resucita permisos; R14-07 menor de edad requiere reglas reforzadas; R14-08 respuesta DSAR respetando plazos y verificación.

### 7. Métricas y resultados que se deben medir
Tiempo hasta revocación efectiva, consultas de datos sin autorización (0), tasa de expedientes DSAR dentro de plazo, errores de reconciliación, entendimiento de usuario. No confundir solicitud de supresión con borrado automático de toda información legalmente exigible.

### 8. Privacidad, límites y amenazas a validez
Eventual consistency, restauración desde backup, datos sensibles, borrado irreversible, impersonación en solicitud; intervención humana para casos complejos. No se afirma cumplimiento sin auditoría jurídica.

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

