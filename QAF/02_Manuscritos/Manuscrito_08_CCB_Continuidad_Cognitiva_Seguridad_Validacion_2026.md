# Manuscrito científico-técnico 08
## Cognitive Commerce Bridge III: continuidad cognitiva omnicanal, transición de sesiones, seguridad y validación experimental

**GoToGym / QAF | Especificación de implementación y protocolo experimental | v1.0 | 14-11-2026**
**Aplicaciones:** GoToGtymPrime (Shop) y appdesplegada (Quantum Coach).  
**Naturaleza:** propuesta técnica basada en inspección de código y conversaciones de prueba; no declara resultados de rendimiento ni despliegue realizado.
**Dependencias:** manuscrito 06 (identidad/consentimiento) y manuscrito 07 (broker de conocimiento).

### Resumen
Una conversación puede comenzar como visitante y continuar tras el inicio de sesión. En Prime, vendedor.js conserva un historial visual en sessionStorage bajo una clave única; en Django, CommerceContinuityStore separa los turnos comerciales por sujeto y añade un distintivo de rol al modo vinculado. Este diseño evita parte de la mezcla de memorias del servidor, pero no define explícitamente un protocolo de transición de identidad para el navegador ni un mecanismo de continuidad cognitiva entre la persona y la tienda. Se propone un ciclo de sesión robusto con identidad de época, rotación de conversación, no transferencia automática de diálogos anónimos a memorias personales, continuidad comercial consentida y pruebas adversariales de dos usuarios, revocación y recuperación ante fallos. El método reaprovecha los principios comprobados por código en Business/Admin (ámbitos, fuentes y proyecciones) sin habilitar herramientas de gestión ni memoria privada para el vendedor.

**Palabras clave:** continuidad cognitiva, namespace, zero trust, session fixation, conversación, seguridad, privacidad, SVMCA, pruebas E2E.

### 1. Evidencia y problema
**Observación:** el usuario puede chatear anónimamente, iniciar sesión, ver el nombre en la barra de Shop y continuar en un panel cuyo agente todavía afirma desconocerlo. Repetir la prueba tras minutos de espera no corrigió la situación; activación de flags de Azure no es validación semántica.
**Hipótesis H3:** la ausencia de un evento confiable de transición de identidad, junto con la falta del bridge verificado o la proyección mínima de nombre, impide la experiencia de continuidad personalizada.
**Pregunta:** ¿cómo ofrecer continuidad en el navegador manteniendo separados los contextos anónimo, comercial vinculado, personal, Business y Administrativo?

### 2. Línea base del código
| Fuente | Comportamiento comprobable |
|---|---|
| gotogym/static/js/vendedor.js | guarda el historial visual en sessionStorage con una clave global gtg_vendedor_historial; no se observó una clave distinta por identidad |
| gotogym/vendedor/conversacion.py | crea conversation_id de servidor, cuenta turnos en la sesión, caduca tras 30 minutos |
| gotogym/vendedor/paquete.py | request.user autenticado -> shop_u_*; visitante -> shop_v_*; identidad v2 opcional |
| gotogym/vendedor/views.py | en cada mensaje construye paquete a partir de request real |
| backend/api/commerce_agent/continuity.py | _digest calcula la clave desde sujeto, conversation_id y sufijo de rol cuando COMMERCE_LINKED |
| backend/api/commerce_agent/principal.py | COMMERCE_LINKED exige sujeto shop_u_* y firma de servicio |
| backend/api/commerce_agent/turn.py | usa CommerceContinuityStore y CanonicalConversationPipeline, no el contexto personal de usuario |
| backend/api/superagent/ai_role_isolation.py | contextos separados por tenant, rol, sujeto y conversación |
| backend/api/superagent/business_conversation_context.py | proyecta solo estado relevante, no historial sin límites |
| backend/api/superagent/admin_conversation_context.py | contexto reciente de un actor/conversación autorizados |
| backend/api/superagent/canonical_privacy.py | separa contexto interno de evidencia externa redactada |

**Inferencia importante:** un historial que el navegador pinta después de iniciar sesión no demuestra que Django haya recuperado la misma conversación, ni que ésta tenga autoridad para vincular la cuenta. En sentido inverso, un servidor que mantenga aislados los estados tampoco impide que el navegador muestre mensajes de una cuenta previa si la clave local no cambia.

### 3. Modelo de estados de sesión
Definimos:
- S0 = visitante anónimo, sin identidad personal.
- S1 = usuario autenticado solo en Prime, pero sin vínculo verificable.
- S2 = autenticado y vinculado en Prime y Django, sin scopes consentidos activos.
- S3 = autenticado, vinculado y con scopes autorizados: COMMERCE_LINKED.
- S4 = consentimiento revocado o expirado durante la conversación.
- S5 = logout, sesión caducada o cambio a otra cuenta.

~~~mermaid
stateDiagram-v2
    [*] --> S0
    S0 --> S1: login Prime
    S1 --> S2: vínculo OIDC verificado
    S2 --> S3: consentimiento explícito
    S3 --> S4: revocar / expirar
    S3 --> S5: logout / cambio de usuario
    S4 --> S3: nueva autorización
    S1 --> S5: logout
    S2 --> S5: logout
    S5 --> S0: nueva sesión anónima
~~~

**Invariante T1:** una transición de estado de identidad rota la conversación servidor para ese principal o cambia su espacio de nombres; no se leen turnos de otro rol ni de otro usuario.
**T2:** los mensajes escritos por un visitante pueden seguir visualmente disponibles en esa pestaña si no han cambiado de propietario y existe aviso claro, pero **no se importan automáticamente a la memoria personal**.
**T3:** al cambiar a otra cuenta o cerrar sesión se eliminan/ocultan mensajes privados de la cuenta anterior.
**T4:** el contexto personal se recompone de fuentes canónicas cada turno, no de un historial anterior tomado como autoridad.
**T5:** la revocación de permisos borra o invalida las proyecciones personalizadas antes del siguiente turno.

### 4. Protocolo de transición AUTH_CONTEXT_CHANGED
Se propone implementar una señal de versión de identidad generada por el servidor (identity_epoch), no por el LLM ni un ID aportado por el navegador.

**En Prime**
- Middleware o vista de estado obtiene clase de identidad: anonymous / local_only / linked_no_consent / linked_consented.
- El servidor mantiene una clave de sesión privada para un "epoch" opaco y la incrementa ante login, logout, cambio de usuario o cambio significativo de permisos.
- El cliente consulta GET same-origin /es/vendedor/estado/ (nuevo endpoint propuesto) con CSRF según el método, Cache-Control: no-store, respuesta limitada: {mode, session_epoch, personalization_ready, invitation_required}.
- Si cambia session_epoch, vendedor.js no reutiliza la misma entrada de sessionStorage; genera una partición de historial por epoch o elimina el historial anterior. El epoch no es usuario id, oid, email ni token.
- El chat solicita una conversación nueva con el flag "new" o un reinicio de estado del servidor, y muestra un aviso contextual accesible.
- El servidor no acepta session_epoch enviado por el cliente como autoridad.

**En Django**
- ContinuityStore conserva memoria comercial bajo tenant + role + subject + conversation_id.
- El rol vinculado no se convierte en PERSONAL, y las memorias personales no se insertan en CommerceContinuityStore.
- En cada turno el Cognitive Commerce Bridge resuelve y autoriza una proyección nueva.
- Ante una revocación, los estados COMMERCE_LINKED ya persistidos que podrían incluir contexto personal deben invalidarse o limpiarse; no basta solo con omitir la nueva proyección si el LLM puede leer el historial anterior.
- La continuidad de la persona en la app y la continuidad comercial son vistas separadas de la misma identidad verificada, no la misma bolsa de historial.

### 5. Modelo matemático de continuidad segura
Sea X_t el estado conversacional del vendedor en turno t. Sea P_t la proyección autorizada del perfil en ese turno; A_t, el conjunto vigente de scopes. Sea M_t la memoria comercial del ámbito actual.

Actualización propuesta:

X_(t+1) = F(X_t, pregunta_t, Catalogo_t, P_t, M_t, role_t)

sujeta a:

  role_t in {COMMERCE, COMMERCE_LINKED}
  P_t = empty si role_t != COMMERCE_LINKED
  P_t ⊆ Allowlist(A_t)
  Namespace(X_t) = (tenant, role_t, shop_subject_t, conversation_id_t)
  Namespace(X_t) != Namespace(X_t') para usuarios/roles ajenos.

Criterio de consistencia de sesión:

  StableEpoch(t,t+1) = (principal_t == principal_(t+1))
                        AND (role_t == role_(t+1))
                        AND (consent_version_t == consent_version_(t+1))

Si StableEpoch es falso, no se deben copiar tokens, hechos, historial private-mode o "working hypotheses" al nuevo contexto. Solo puede reanudarse un estado anonimizado y expresamente seleccionado por el usuario.

**Propuesta QAF de decisión de restauración**:
- C_t: coherencia entre identidad actual y propietario del historial (booleano, obligación absoluta).
- I_t: utilidad conversacional del estado que se pretende restaurar (medida en pruebas).
- eta_t: ahorro relativo de preguntas repetidas por evidencia consentida.
- S_t: incertidumbre sobre origen/vigencia del dato.
La restauración se permite solo si C_t = 1 y no hay conflicto de finalidad; los otros indicadores optimizan la experiencia dentro del conjunto seguro. Ninguna suma ponderada puede compensar C_t = 0.

### 6. Reutilización de Business/Admin: patrón, no permisos
El rol BUSINESS se resuelve contra membresía activa de organización y restringe herramientas de negocio; ADMIN se limita a usuarios y acciones administrativas autorizadas. Para Commerce se adopta el mismo patrón:
- contexto inmutable de rol y propietario;
- selección mínima de evidencias por pregunta;
- historial reciente limitado y por conversación;
- distinción entre evidencia histórica y hechos actuales;
- auditoría y guardrails antes de narración;
- escritura reversible, sujeta a confirmación humana.

No se debe conceder Business read, Admin read, personal.memory.write ni herramientas de salud al rol COMMERCE_LINKED. El usuario puede pedir "qué sabes de mí", pero la respuesta solo enumera categorías de datos permitidas y hechos ya autorizados, no toda su historia personal.

### 7. Matriz de amenazas y controles
| Amenaza | Escenario | Control indispensable |
|---|---|---|
| Cambio de cuenta en pestaña compartida | La persona B ve historial de A | Epoch por sesión, limpieza de UI, separación de servidor |
| Account linking indebido | Coincidencia de correo crea vínculo de identidad | Par issuer + oid, prueba de posesión y revisión JIT |
| Confused deputy | Credencial del vendedor lee memoria PERSONAL | Broker interior gobernado; Commerce no puede llamar personal.read |
| Replay | Reenvío de aserción firmada | iat, exp <=60 s, jti atómico en cache compartida |
| Elevación de scope | Cliente envía scopes extra o cambia consent_version | Consentimiento resuelto en Prime y forma cerrada en Django |
| Prompt injection | Historia/catálogo incluye instrucciones maliciosas | Tratar evidencia como dato; validación de respuesta y acciones |
| Consentimiento revocado | Un estado cacheado sigue usando hechos anteriores | Invalidación por scope/versión/epoch; nueva proyección cada turno |
| Filtración mediante logs | Telemetría registra PII o secretos | Solo códigos enumerados, request_id, sin preguntas o perfiles |
| Conversación cruzada | Reutilizar conversation_id ajeno | ID emitido por servidor; digest sujeto+rol+conversación |
| Desincronización entre servicios | Prime vinculado, Django sin vínculo | Fallo en modo anónimo y diagnóstico seguro |
| Denegación por infraestructura | Cache/Redis no disponible | Falla cerrada de identidad; catálogo público opera si es seguro |
| Falsa identificación por LLM | Modelo responde "sé tu nombre" sin evidencia | Hecho de identidad requerido, respuesta verificable |

### 8. Algoritmo de transición
~~~python
def on_commerce_request(request, session_state, now):
    principal = trusted_principal_from_django_session(request)
    classification = classify_commerce_identity(principal)  # sin datos del navegador
    consent_v = active_consent_version_or_zero(principal)
    current_epoch = (classification, principal.internal_session_key, consent_v)
    previous_epoch = session_state.get("commerce_epoch_binding")

    if previous_epoch != current_epoch:
        # Sin heredar privilegios ni historial del principal anterior.
        session_state["commerce_epoch_binding"] = current_epoch
        session_state["vendedor_conversacion"] = new_server_conversation(now)
        session_state["commerce_client_epoch"] = opaque_random_nonce()

    return session_state["commerce_client_epoch"]
~~~

**Precaución de diseño:** el identificador de epoch enviado a la UI debe ser un nonce aleatorio y no una representación reutilizable de IDs personales. Evitar duplicar esta lógica entre view y middleware; hacer una única autoridad del estado.

### 9. Contrato de observabilidad mínima
Proponer eventos de cardinalidad baja:
- commerce.chat_turn.ok; commerce.chat_turn.error
- commerce.identity.anonymous / local_only / verified / rejected
- commerce.identity.reason_code (sin PII)
- commerce.context.scope_count, fact_count, withheld_count
- commerce.context.revocation_effective
- commerce.session.transition, reset, conflicting_epoch
- commerce.safety.cross_subject_denied
- commerce.experience.personalization_accepted

No registrar textos de las preguntas, respuestas, nombre, correo, oid, claims OIDC, secret ni memorias. Correlacionar con request_id de corto alcance y trazas de servicio, evitando IDs persistentes en dashboards. Definir tableros de conversión sin unir la telemetría de bienestar a publicidad individual.

### 10. Experimentos y validación E2E
Proponer un corpus de 60 recorridos: 20 identidad/consentimiento, 20 continuidad/memoria, 20 seguridad/resiliencia. Dos usuarios sintéticos A y B, uno con cuenta legacy; incluir conversación guest->login->logout->nuevo login, sesiones en varias pestañas y permisos revocados.

| Código | Recorrido | Criterio |
|---|---|---|
| E01 | Visitante consulta productos | Respuesta comercial correcta, sin perfil |
| E02 | Visitante inicia sesión y cuenta vinculada | Cambia modo al siguiente turno, tras consentimiento |
| E03 | Usuario inicia sesión con cuenta Prime local sin enlace | No se autovincula; muestra acción útil de enlace |
| E04 | Usuario inicia sesión como A, luego como B en la misma pestaña | B nunca ve historial privado de A |
| E05 | A desactiva permiso durante chat | Datos de scope revocado ausentes inmediatamente |
| E06 | Nombre autorizado y presente en User.full_name | Saluda con nombre correcto sin volver a preguntar |
| E07 | Nombre ausente en perfil | Pregunta cómo desea ser llamado, no lo adivina |
| E08 | Deporte y compras autorizados | Recomienda prendas reales con procedencia del catálogo |
| E09 | Memoria episódica no autorizada | No lee ni revela anécdotas personales |
| E10 | Fecha de experiencia caducada | No la presenta como preferencia vigente |
| E11 | Perfil Django con dos correos similares | Solo identifica por issuer/oid |
| E12 | Caída de Redis working_state | No acepta replay ni personaliza sin prueba confiable |
| E13 | Error de Django comercial | UI ofrece reintentar sin exponer diagnóstico privado |
| E14 | Chat extendido y paginación | No sobrepasa límites ni mezcla roles |
| E15 | Solicitud administrativa dentro de Shop | Deniega acción y mantiene rol comercial |
| E16 | Pregunta sobre métricas clínicas | Rechaza uso comercial de salud no consentida |
| E17 | Login desde otra pestaña | Detecta cambio o reinicia en interacción siguiente |
| E18 | Browser history restaurado después de 30 minutos | Descartar historial caducado y resetear contexto |
| E19 | Consentimiento caducado anual | No interpreta un toggle antiguo como autorización |
| E20 | Key Vault rota clave | Servicio y aserciones continúan con ventana de transición segura |

**Métricas primarias** (todas sujetas a ensayo, no resultados): tasa de reconocimiento correcto, porcentaje de turnos sin repetición de preguntas ya respondidas y autorizadas, cero mezclas entre usuarios, revocación efectiva a primer turno, latencia P95, tasa de respuestas sin evidencia, porcentaje de sugerencias con respaldo en catálogo. Medir utilidad comercial mediante evaluación humana ciega antes de inferir incremento de conversión.

### 11. Diseño experimental QAF y decisiones
Se propone una comparación por cohortes:
- Control: COMMERCE, sin datos personales.
- Grupo P: COMMERCE_LINKED con perfil básico autorizado.
- Grupo M: COMMERCE_LINKED con broker de conocimiento ampliado opt-in.
El usuario se asigna solo si hay consentimiento; sin consentimiento queda en control, nunca se fuerza.
Resultado de experiencia Y = correcta_recomendacion + no_repeticion + satisfacción; se reportan componentes por separado para evitar pesos arbitrarios. Valor causal incremental de M frente a P exige muestra y control de sesgo. La función QAF decide **qué evidencia recuperar**, no el consentimiento, que es una restricción absoluta.

### 12. Secuencia de implementación y plan de liberación
**Fase 0 — diagnóstico y guardrails:** ejecutar preflight Prime, comando de identidad, commerce_readiness Django y verificar CI; obtener motivo real de fallbacks en cuenta de prueba. Sin modificar usuarios ni secretos.
**Fase 1 — vínculo:** verificar ambas tablas ExternalIdentityLink con issuer+oid, JIT seguro y permisos vigentes. Prueba H1 del manuscrito 06.
**Fase 2 — contexto mínimo:** agregar presentación de nombre autorizado y preferencias al Context Broker, medir exactitud y comportamiento de fallback. Prueba H2 del manuscrito 07.
**Fase 3 — transición:** gestionar cambio de identidad/epoch en vendedor.js y conversacion.py; probar guest->login y logout.
**Fase 4 — memoria:** habilitar proyección seleccionada por finalidad en canario opt-in, sin abrir MemoryRetriever a Commerce.
**Fase 5 — aceptación:** ensayos en PostgreSQL/Redis reales de staging, revisión de seguridad, gradualidad, alertas y rollback.

Los flags de infraestructura existentes se deben interpretar como condición de habilitación, no como prueba funcional:
- VENDEDOR_CONTRATO_V2 (Prime).
- COMMERCE_LINKED_CONTEXT_ENABLED (Django).
- COMMERCE_AGENT_ENABLED (Django).
La reversión de funciones no implica borrar perfiles o contraseñas ni apagar el servicio comercial.

### 13. Estructura de cambios y contratos
**Prime**: gotogym/static/js/vendedor.js; gotogym/gotogym/templates/partials/_vendedor_panel.html; gotogym/vendedor/conversacion.py; gotogym/vendedor/views.py; gotogym/vendedor/context_processors.py; gotogym/vendedor/personalizacion.py. Se propone nuevo vendedor/estado.py para clasificar y exponer estado limitado.
**Django**: backend/api/commerce_agent/continuity.py; principal.py; views.py; turn.py; evidence.py; narration.py; knowledge_bridge.py (nuevo); commerce_knowledge_policy.py (nuevo).
**Pruebas Prime**: gotogym/vendedor/test_identidad.py, test_consentimiento.py, nuevas test_session_transitions.py y test_vendedor_epoch.py.
**Pruebas Django**: backend/api/test_commerce_linked_context.py, nuevas test_commerce_knowledge_bridge.py, test_commerce_isolation.py y pruebas de cache.
No se debe declarar un test existente bajo un nombre propuesto.

### 14. Plan de recuperación y aceptación productiva
Antes de activar en todos los usuarios:
- CI y tests de seguridad sin fallos.
- Prueba humana documentada en cuenta de ensayo verificada.
- Métricas de no reconocimiento clasificadas con códigos concretos.
- Auditoría de retiro de consentimientos.
- 0 filtraciones en suites de dos usuarios y 0 intentos autorizados por correo.
- Entradas de log con formato seguro.
- Backout probado para ambos flags, manteniendo chat comercial operativo.
- Plan de migración aditiva y reversión sin pérdida de planes, claves, historial ni registros de usuario.

### 15. Limitaciones y amenazas a validez
Inspección estática no equivale a ejecución productiva. La memoria del navegador puede persistir por pestaña, pero el estado del servidor depende de cookie/rol/subject, y la ejecución real requiere logs y DB. Los índices C, I, eta y S son métricas operacionales propuestas, no demostración de computación cuántica. Los resultados experimentales quedan en blanco hasta ejecutar el protocolo. La intervención podría producir una mejora de satisfacción, pero también aumentar latencia o percepción de invasión; hay que medir ambos efectos.

### 16. Referencias de ingeniería y estándares
1. GoToGtymPrime: gotogym/static/js/vendedor.js; gotogym/vendedor/conversacion.py; paquete.py; identidad.py; personalizacion.py.
2. appdesplegada: backend/api/commerce_agent/continuity.py; principal.py; views.py; turn.py; context_broker.py.
3. appdesplegada: backend/api/superagent/ai_role_isolation.py; business_conversation_context.py; admin_conversation_context.py; canonical_privacy.py.
4. NIST SP 800-63-4 / 63C-4, identidad y federación: https://pages.nist.gov/800-63-4/
5. OWASP ASVS 5.0.0: https://asvs.owasp.org/
6. RFC 2104 HMAC: https://www.rfc-editor.org/rfc/rfc2104
7. OpenID Connect Core 1.0: https://openid.net/specs/openid-connect-core-1_0.html
8. Manuscrito 06 de esta serie (identidad); Manuscrito 07 (knowledge broker); manuscritos históricos QAF/02_Manuscritos/Manuscrito_03_Continuidad_Cognitiva_Omnicanal_Quantum_Coach_Prime.pdf y Manuscrito_04_Alta_Costura_Inteligente_Tallaje_QAF_Prime.pdf.

**Resultado buscado:** continuidad percibida por el usuario, sin degradación de privacidad ni privilegios cruzados, con identidad personal efectiva, memoria relevante y respuestas del vendedor fundamentadas.