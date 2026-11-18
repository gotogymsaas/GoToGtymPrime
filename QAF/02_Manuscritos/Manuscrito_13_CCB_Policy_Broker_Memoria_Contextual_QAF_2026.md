# Manuscrito científico-técnico 13 — Cognitive Commerce Bridge / QAF
## Broker cognitivo por finalidad y selección QAF de memorias para el vendedor
**Fecha:** 14 noviembre 2026 · **Autor institucional:** GoToGym, Friends N Gifts S.A.S. · **Estado:** propuesta técnica, funciones validadas solo cuando su PR y pruebas lo acrediten.

### Resumen
Formula un selector que consulta únicamente evidencias personales de comercio bajo identidad validada, sin otorgar al vendedor permisos del Coach personal o Business/Admin. Integra perfil básico, preferencias confirmadas, experiencias y memoria comercial con procedencia, caducidad y clasificación de sensibilidad. El ranking QAF se ejecuta solo sobre un conjunto autorizado de hechos.

### 1. Problema de ingeniería y evidencia de código
La proyección vigente permite nombre, deporte y algunas preferencias, pero no resúmenes completos de contexto. El usuario solicita atención continua y tallaje; la tentación de abrir acceso directo a MemoryRetriever personal supondría una escalada de privilegios. La especialización por rol de Business y Administrativo es una referencia para mantener límites.

### 2. Hipótesis falsable
La evidencia relevante con propietario y finalidad verificados ofrece respuestas personalizadas más correctas que un vendedor anónimo, sin introducir información sensible no solicitada.

### 3. Marco formal, variables e invariantes
```text
Eligible(f) = VerifiedOwner(f) AND AllowedScope(f) AND Current(f)
              AND CommercePurpose(f) AND NonSensitive(f) AND SourceAllowed(f)
Utility(f,q) = 0.40*relevance + 0.25*confidence + 0.20*freshness + 0.15*decision_value
X* = argmax Σ_(f in X) Utility(f,q)
subject to Eligible(f)=true; |X|<=8; token_budget<=700.
No peso de Utility puede volver elegible un hecho prohibido.
```

### 4. Arquitectura e integración entre repositorios
Authority Django: `context_broker.py` construye CommercialFact. `knowledge_bridge.py` selecciona y limita evidencia. `evidence.py` entrega `commerce_customer_context` al rol COMMERCE_LINKED; `narration.py` utiliza datos pero no abre herramientas `personal.read`. El contexto de Business/Admin no es compartible mediante un permiso comercial. El contenido es información no confiable, nunca instrucciones de sistema.

### 5. Algoritmos de referencia
```python
def project(q, linked_identity, source):
    if linked_identity is None: return None
    facts = []
    if allows("profile.basic"): facts += basic_profile(source)
    if allows("sports.preferences") and owner_enabled_memory():
        facts += confirmed_sports_knowledge(source)
    if allows("experiences.commerce_guidance"):
        facts += completed_experience_flags_only(source)
    if allows("tailoring.measurements"):
        facts += validated_size_hint_from_prime()
    safe = [f for f in facts if all_authorization_checks(f)]
    return qaf_rank(safe, q, max_items=8)
```

### 6. Mapa de cambios implementables
Django `backend/api/commerce_agent/{identity,context_broker,knowledge_bridge,evidence,narration,turn}.py`; Prime `gotogym/vendedor/{identidad,paquete,personalizacion,talla}.py`. El subtipo de completitud Exp006/012/013 se incorpora detrás de un scope nuevo; nunca se exportan resultados de fotos o keypoints.

### 7. Protocolo de pruebas y aceptación
L13-01 perfiles de A/B no se mezclan; L13-02 sin scope no se ejecuta query privada; L13-03 revocación corta la proyección siguiente; L13-04 score alto de dato médico sigue siendo inelegible; L13-05 evidencia sin procedencia se excluye; L13-06 talla solo si medidas confirmadas; L13-07 prompt injection en conocimiento se trata como dato; L13-08 sólo un máximo de 8 hechos; L13-09 regresión de roles BUSINESS/ADMIN; L13-10 solicitud de memoria completa resulta en resumen permitido o negativa.

### 8. Métricas científicas y umbrales de validación
C-coherencia = afirmaciones respaldadas / afirmaciones personalizadas; I-impacto = mejora de utilidad comercial en ensayo; η-eficiencia = hechos usados/hechos leídos; S-entropía descriptiva de fuentes. Las ecuaciones son ingeniería heurística, no computación cuántica ni prueba de causalidad.

### 9. Amenazas a validez, seguridad y privacidad
Fuga accidental por LLM, sesgo de preferencias inferidas, datos caducados, límites temporales, sobreexposición de la memoria episódica. Debe obtenerse autorización para nuevas finalidades antes de ampliar el broker.

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

