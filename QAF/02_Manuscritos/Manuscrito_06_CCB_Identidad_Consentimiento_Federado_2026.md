# Manuscrito científico-técnico 06
## Cognitive Commerce Bridge I: identidad federada verificable, vinculación bidireccional y consentimiento de finalidad

**GoToGym / QAF | Diseño técnico de implementación | Versión 1.0 | 14-11-2026**
**Repositorios auditados:** gotogymsaas/GoToGtymPrime (nombre real del repositorio) y gotogymsaas/appdesplegada.  
**Estado epistemológico:** arquitectura propuesta y análisis estático de código; NO equivale a experimento en producción ni a funcionalidad desplegada.
**Área:** identidad digital, autorización, seguridad por diseño, agentes comerciales con IA.

### Resumen
Se estudia la discrepancia observada entre una sesión autenticada en GoToGym Prime, visible en la cabecera de Shop, y un Quantum Coach comercial que responde sin conocer el nombre ni el perfil de la misma persona. El código separa correctamente autenticación de aplicación, afirmación de identidad entre servidores, resolución del usuario en Django y permisos de finalidad. Sin embargo, los fallos de enlace o consentimiento hacen que el agente continúe en modo anónimo y no existe una señal de diagnóstico comprensible para el operador y el usuario. Se propone una pasarela de identidad vinculada al emisor y sujeto federado de Microsoft Entra External ID, con control de permisos versionados, estados explícitos, auditoría sin datos personales y recuperación progresiva para usuarios existentes. El objetivo no es copiar contraseñas o cuentas, sino demostrar de forma reproducible que una identidad autentica la misma persona en Prime y en Django antes de solicitar conocimiento privado.

**Palabras clave:** OIDC, Entra External ID, issuer, oid, HMAC-SHA256, consentimiento, JIT, fail-closed, continuidad cognitiva, QAF.

### 1. Pregunta, hipótesis y alcance
**Pregunta:** ¿Por qué una sesión de Shop con nombre visible sigue generando respuestas anónimas del agente?
**Hipótesis H1:** la autenticación en Prime no implica que exista una cadena de identidad/comercialización válida en ambas bases de datos. La condición de enlace y los permisos se evalúan independientemente. Esta hipótesis se comprobará mediante indicadores booleanos y pruebas sobre un usuario de ensayo, sin afirmar que se haya establecido aún la causa concreta de producción.

No se modifica Microsoft Entra, la base de usuarios ni las contraseñas mediante este manuscrito. No se debe inventar un vínculo basándose en correo o nombre. No se debe copiar un token OIDC del navegador al agente ni conceder permisos por poseer la credencial de servicio.

### 2. Evidencia del estado de implementación
| Componente | Fuente de código inspeccionada | Consecuencia |
|---|---|---|
| Identidad de sesión en Shop | gotogym/vendedor/paquete.py: sujeto_del_visitante | request.user.is_authenticated y sujeto shop_u_* no demuestran una identidad OIDC vinculada |
| Emisión federada | gotogym/vendedor/identidad.py: emitir | Se requiere usuario autenticado, credencial, GOTOGYM_OIDC.ISSUER, ExternalIdentityLink y scopes activos |
| Consentimiento en Shop | gotogym/vendedor/consentimiento.py | GET/POST con CSRF; emite linked y scopes; permiso concedido no equivale a vínculo |
| Consentimiento visual | gotogym/vendedor/personalizacion.py y template _personalizacion.html | La persona puede activar/revocar scopes y ver vencimiento |
| Vinculación Entra | gotogym/gotogym_oidc/views.py | Entra determina issuer + subject; la coincidencia de email requiere prueba adicional |
| Verificación en Django | backend/api/commerce_agent/identity.py | Verifica HMAC, audiencia, tiempo, replay, issuer, oid y cuenta activa; ante fallo devuelve None |
| JIT en Django | backend/universal_identity/adapter.py y gotogym_oidc/views.py | Puede vincular cuentas existentes por mapeo JIT preparado; no debe migrar por email ambiguo |
| Contexto comercial | backend/api/commerce_agent/views.py | La falla de identidad conserva el servicio comercial anónimo |

Se observa una **inconsistencia de política**: el documento docs/identity/COMMERCE_OMNICHANNEL_V2_FOUNDATION.md dice que ningún scope se concede por defecto, pero vendedor/consentimiento.py dispone de conceder_al_crear_perfil() y vendedor/apps.py lo conecta a la señal perfil_creado. El flujo actual puede conceder cinco scopes tras la aceptación inicial de términos. Antes de cambiar el producto debe decidirse una única política explícita, versionada y demostrable; términos generales no equivalen necesariamente a autorización granular de consulta de memorias.

### 3. Modelo formal de identidad y consentimiento
Definimos:
- U_P: usuario local Prime; U_D: usuario existente appdesplegada.
- k = (issuer, oid): par inmutable de identidad federada verificado en servidor.
- L_P(U_P,k), L_D(U_D,k): vínculos registrados y activos en cada aplicación.
- C(U_P,s,t,v): consentimiento vigente en Prime para scope s, versión v, instante t.
- E(x): aserción firmada con clave de identidad exclusiva.
- V(E): verificación criptográfica, audiencia, frescura, unicidad jti, emisor y vínculo.
- S: conjunto de scopes comerciales permitidos.

La autorización para exportar un hecho f se define como:

A(f,U_P,U_D,k,t) = Auth_P(U_P,t) AND L_P(U_P,k) AND L_D(U_D,k) AND V(E)
                   AND C(U_P,scope(f),t,v) AND Purpose(f,"commerce")
                   AND Owns(U_D,f) AND Fresh(f,t) AND PolicyAllow(f).

**Invariante I1:** el modo personalizado existe solo cuando A es verdadero para al menos un scope; para cualquier otra condición el resultado es COMMERCE, sin campos privados.  
**Invariante I2:** la credencial de servicio no concede identidad humana.  
**Invariante I3:** el emisor y el oid se verifican en ambas bases; nunca se utiliza correo, username o nombre como sustituto.  
**Invariante I4:** el consentimiento puede revocarse de inmediato en el turno siguiente; ningún dato desautorizado se reutiliza en caché, historial o prompt.  
**Invariante I5:** ni el identificador interno de Django ni sus planes, contraseñas y datos de salud salen como atributos del agente.

### 4. Protocolo propuesto CCB-ID v1
El contrato comercial v2 y la firma de servicio existentes permanecen intactos. La identidad es un segundo bloque criptográfico. Se conservan los encabezados X-Coach-Key-Id, X-Coach-Timestamp y X-Coach-Signature para autenticación de servicio, y por separado VENDEDOR_IDENTIDAD_CLAVE_ID/SECRETO versus COMMERCE_IDENTITY_KEY_ID/SECRET para la aserción de persona.

~~~json
{
  "schema_version": 2,
  "visitor": {"subject": "shop_u_<digest>", "authenticated": true},
  "conversation_id": "shop-<uuid>",
  "identity": {
    "key_id": "shop-prime-identity-1",
    "assertion": "<base64url(payload-servidor)>",
    "signature": "<hmac-hex>"
  },
  "customer_context": {"size_hint": null}
}
~~~

La aserción verificada contiene iss, aud, idp_issuer, idp_subject, scopes, consent_version, iat, exp y jti; vida máxima actualmente 60 segundos. La clave de identidad debe ser independiente de commerce-service-secret y OIDC_CLIENT_SECRET. El servidor Django verifica firma y replay antes de resolver la relación local; no permite que el navegador declare scopes arbitrariamente.

**Propuesta de extensión sin ampliar privilegios:** añadir a la trazabilidad interna un estado estructurado de resolución, nunca la aserción ni su contenido:
- shop_session_anonymous
- prime_oidc_link_missing
- prime_consent_missing
- prime_consent_expired
- prime_assertion_emitted
- coach_issuer_mismatch
- coach_unknown_identity_key
- coach_signature_invalid
- coach_replayed_assertion
- coach_oidc_link_missing
- coach_linked_context_ready

Los estados se envían únicamente a telemetría privada o a una interfaz de diagnóstico con permiso administrativo. El usuario solo ve una invitación segura a vincular cuenta o ajustar permisos; jamás un oid ni un identificador de base de datos.

### 5. Algoritmo determinista de diagnóstico
~~~python
def evaluate_prime_readiness(*, request_user, issuer, identity_key_ready, consent, link):
    if not request_user.is_authenticated:
        return "shop_session_anonymous"
    if not issuer or not identity_key_ready:
        return "configuration_incomplete"
    if link is None or link.issuer != issuer:
        return "prime_oidc_link_missing"
    if consent is None:
        return "prime_consent_missing"
    scopes = consent.active_scopes()
    if not scopes:
        return "prime_consent_expired"
    return "prime_assertion_ready"
~~~

La evaluación se hace cada turno, no una sola vez al cargar el HTML; se utilizan identidades resueltas por middleware/servidor. Se propone instrumentar vendedor/identidad.py y exponer una comprobación administrativa de solo lectura. **No se recomienda habilitar vinculaciones por coincidencia de email en producción.**

### 6. Migración JIT y cuentas antiguas
1. Elaborar inventario de usuarios Prime autenticados por login legado, cuentas Prime con ExternalIdentityLink, usuarios Django con ExternalIdentityLink y registros de consentimiento.
2. Para cada identidad existente que necesite vinculación, usar un flujo OIDC autenticado con prueba de posesión de la cuenta local o JIT preparado por operador autorizado.
3. Rechazar vínculos si hay dos cuentas locales con el mismo correo, identidades conflictivas, oid ya asociado a otro usuario o emisor no coincidente.
4. No sobrescribir el usuario ni el plan Django; agregar solamente relación verificada de identidad.
5. No convertir una cuenta vieja en "consentida" por inferencia. Mostrar la pantalla de permisos de Prime y registrar una decisión afirmativa con fecha, versión de texto y scopes.
6. Hacer doble comprobación U_P -> k -> U_D sin exponer IDs en el cliente.

**Riesgo de diseño:** Prime permite login local y OIDC. Por ello una cabecera que muestra nombre representa una cuenta local válida, pero no prueba que el login haya pasado por el proveedor central. El estado "reconocido en Prime" no es sinónimo de "perfil personal disponible en Django".

### 7. Política de consentimiento verificable
Se propone ConsentDecision con: actor local, scope, granted, granted_at, expires_at, consent_version, policy_version, source_ui, revoked_at y audit_event_id. La fuente operativa puede permanecer en CommercePersonalizationConsent; estos campos son una evolución aditiva, no una migración destructiva. El texto de interfaz debe describir por separado: perfil básico; preferencias; experiencias; medidas voluntarias; memoria comercial. Incorporar display_name requiere notificar y versionar el alcance, porque hoy "profile.basic" solo describe deporte, horario y actividad.

Separar:
- Autenticación: prueba de quién eres.
- Autorización: qué se puede consultar.
- Consentimiento: para qué categoría y finalidad.
- Proyección: qué campos concretos necesita cada respuesta.

### 8. Plan de cambios por repositorio
**Prime**
- gotogym/vendedor/identidad.py: añadir códigos estructurados y métricas cardinalidad controlada.
- gotogym/vendedor/consentimiento.py: unificar política de opt-in, decisión explícita y revocación.
- gotogym/vendedor/personalizacion.py: estado visible "Conectado", "Falta vincular", "Falta autorizar", sin información sensible.
- gotogym/gotogym_oidc/views.py: integración de cuenta local mediante prueba y enlace verificado.
- gotogym/vendedor/test_identidad.py, test_consentimiento.py: regresiones de permisos y emisión.

**appdesplegada**
- backend/api/commerce_agent/identity.py: diagnóstico de fallos por etapa y correlación con request_id, sin PII.
- backend/api/commerce_agent/views.py: señales de contexto vinculado/proyectado.
- backend/universal_identity/jit_verify.py: verificar mapeos preexistentes, sin modificar cuentas.
- backend/api/test_commerce_linked_context.py: pruebas cruzadas con issuer + oid y revocación.

### 9. Plan experimental y métricas falsables
Se evalúa en staging sobre cuentas sintéticas A/B/legacy y después canario humano; no se declaran resultados antes de ejecutarlos.

| Ensayo | Condición | Resultado exigido |
|---|---|---|
| T01 | Visitante sin login | Respuesta comercial útil; cero datos personales |
| T02 | Login legado Prime sin vínculo OIDC | Diagnóstico "prime_oidc_link_missing"; ninguna inferencia por correo |
| T03 | Cuenta vinculada en Prime pero no Django | "coach_oidc_link_missing"; sin datos privados |
| T04 | Ambos vínculos y permiso activo | Proyección mínima y trazable |
| T05 | Consentimiento revocado | Ningún campo revocado en el siguiente turno |
| T06 | Firma alterada o jti repetido | Rechazo y fallback controlado |
| T07 | Mapeo JIT conflictivo | Bloqueo; cuentas y planes intactos |
| T08 | Dos cuentas con mismo nombre o correo parecido | Nunca se mezclan identidades |
| T09 | Nombre de usuario no incluido en proyección | Respuesta no debe inventarlo |

Indicadores de aceptación propuestos (metas, NO resultados): tasa de identidad resuelta >=99% entre sesiones elegibles verificadas en canario; filtraciones entre sujetos = 0 en pruebas adversariales; afirmaciones de perfil sin evidencia = 0; latencia P95 adicional del puente <=150 ms para datos relacionales cacheados (objetivo a medir, no promesa).

### 10. Seguridad, privacidad y reversibilidad
Despliegue en etapas: shadow de diagnósticos -> test de vinculación -> canario 1-5% -> 25% -> 100%, cada etapa con aprobación y métricas. Las banderas existentes VENDEDOR_CONTRATO_V2 y COMMERCE_LINKED_CONTEXT_ENABLED son reversibles; apagarlas no elimina usuarios, cuentas, planes ni memorias. No registrar tokens, correos, nombres, medidas, secrets ni prompts en logs. El monitoreo debe usar request_id, códigos enumerados, métricas agregadas y hashes de baja correlacionabilidad si son imprescindibles. No usar flags "true" como prueba de funcionamiento.

### 11. Limitaciones
Se dispone de evidencia estática del código y capturas de una conversación, pero no de observabilidad en producción ni de consultas de base de datos. No se conoce aún si el incidente específico es falta de vínculo Prime, consentimiento, vínculo Django o filtrado del broker. La extensión de consentimiento y la vinculación de cuentas son propuestas sujetas a revisión legal/privacidad. No se afirma novedad científica demostrada ni mejora de KPIs antes de ensayos.

### 12. Bibliografía y artefactos reproducibles
1. NIST SP 800-63-4, Digital Identity Guidelines, edición final 2025: https://doi.org/10.6028/NIST.SP.800-63-4
2. NIST SP 800-63C-4, Federation and Assertions: https://pages.nist.gov/800-63-4/sp800-63c.html
3. OpenID Connect Core 1.0, issuer/subject y validación de tokens: https://openid.net/specs/openid-connect-core-1_0.html
4. RFC 2104, HMAC: https://www.rfc-editor.org/rfc/rfc2104
5. OWASP ASVS 5.0.0, controles de autenticación y autorización: https://asvs.owasp.org/
6. GoToGtymPrime: gotogym/vendedor/identidad.py; consentimiento.py; personalizacion.py; gotogym_oidc/views.py.
7. appdesplegada: backend/api/commerce_agent/identity.py; views.py; backend/universal_identity/adapter.py.
8. Manuscritos históricos QAF/02_Manuscritos/Manuscrito_01_Identidad_Federada_Identity_Bridge_GoToGym.pdf y Manuscrito_02_Contexto_Comercial_Personalizacion_QAF.pdf; relacionados por temática, no validados experimentalmente aquí.

**Salida requerida de implementación:** identidad comercial verificada de extremo a extremo, motivo exacto de fallback y consentimiento explícito y revocable. Su aceptación precede a toda exportación de conocimiento personal.