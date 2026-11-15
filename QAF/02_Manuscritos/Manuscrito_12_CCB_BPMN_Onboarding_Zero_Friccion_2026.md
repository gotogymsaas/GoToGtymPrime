# Manuscrito científico-técnico 12 — Cognitive Commerce Bridge / QAF
## Orquestación BPMN: de identidad universal a atención contextual y compra sin pasos redundantes
**Fecha:** 14 noviembre 2026 · **Autor institucional:** GoToGym, Friends N Gifts S.A.S. · **Estado:** propuesta técnica, funciones validadas solo cuando su PR y pruebas lo acrediten.

### Resumen
Diseña un coordinador de procesos que consume estados verificables de Entra, contrato y Decision API para mostrar únicamente la acción faltante en cada momento. El sistema mantiene venta y soporte disponibles aunque el usuario rechace personalización. Su contribución es separar experiencia de usuario de políticas y preservar el histórico de interacciones al cambiar de sesión.

### 1. Problema de ingeniería y evidencia de código
En APP y Shop existen pantallas y sesiones distintas. Un usuario autenticado que llega al chat puede estar desvinculado en Django o no haber autorizado la finalidad. Navegar a varias pantallas en lugar de resolver el siguiente paso dentro de una sola experiencia rompe continuidad.

### 2. Hipótesis falsable
La reducción de pasos redundantes sustentados en decisiones válidas disminuye el tiempo hasta atención útil sin disminuir comprensión, revocabilidad o éxito de comprobación de identidad.

### 3. Marco formal, variables e invariantes
```text
State = {GUEST, AUTH_LOCAL, LINK_REQUIRED, CONTRACT_REQUIRED,
OPTIONAL_PERMISSION_REQUIRED, READY_BASIC, READY_TAILORING, REVOKED}
State_t+1 = Transition(State_t, VerifiedEvent_t, PolicyVersion_t)
Invariant: optional_permission_denied => catalog_and_checkout_available.
Invariant: changed_subject => new_conversation_epoch; no history across users.
Friction F = prompts_shown / necessary_user_decisions.
Minimize E[F] subject to zero unauthorized reads and full receipt retention.
```

### 4. Arquitectura e integración entre repositorios
Primero consulta sesión (sin datos privados); luego vínculo OIDC validado en Prime y Django; luego documento contractual aplicable; luego permisos opcionales pertinentes; por último, servicio de contexto. En los estados de consentimiento opcional, no bloquear catálogo. UI de un solo paso con CTA verificable y reentrada al chat, no abrir ventanas sin controlar origen ni prometer deep links inexistentes.

### 5. Algoritmos de referencia
```python
def next_step(session, policy, verified_scope):
    if session.anonymous: return ("GUEST_ASSIST", [])
    if not session.linked: return ("LINK_ACCOUNT", ["continue-shopping"])
    if not session.accepted(policy.contract_version):
        return ("READ_AND_ACCEPT_CONTRACT", ["continue-general"])
    if verified_scope is None or not verified_scope.is_valid:
        return ("OPTIONAL_PERSONALIZATION", ["accept", "not-now"])
    return ("READY", ["consult-authorized-context"])
```

### 6. Mapa de cambios implementables
Prime: `gotogym/vendedor/estado.py`, `conversacion.py`, `views.py`, `static/js/vendedor.js` y panel de Mi Cuenta; Django: contrato `commerce_agent/identity.py`, `context_broker.py`; API de estado no debe incluir nombre, oid, email, medidas o historia. Rutas de alta costura solo se anuncian cuando están registradas y disponibles en APP.

### 7. Protocolo de pruebas y aceptación
L12-01 visitante -> chat general; L12-02 autenticado sin link -> una sola CTA de enlace; L12-03 contrato esencial no vigente -> lectura explícita; L12-04 opt-in negado -> pago disponible; L12-05 opt-in válido -> no re-preguntar; L12-06 login a mitad del chat -> epoch nuevo; L12-07 cambio de cuenta -> UI limpia; L12-08 token caducado -> estado seguro; L12-09 idioma ES/EN y accesibilidad WCAG; L12-10 caída del motor -> venta genérica.

### 8. Métricas científicas y umbrales de validación
Tiempo desde login hasta primera respuesta relevante, número de decisiones redundantes, éxito de reentrada post-enlace, tasa de abandono de checkout, comprensión de consentimiento, tasa de fallbacks identificados por código. No usar clicks forzados como métrica de consentimiento.

### 9. Amenazas a validez, seguridad y privacidad
Dark patterns, bloqueo inadvertido de pago, cache del navegador, accesibilidad en móvil, sesión OIDC antigua o doble cuenta. La UX debe conservar rechazo claro y funcionamiento general.

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

