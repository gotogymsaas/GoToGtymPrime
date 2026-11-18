# Manuscrito científico-técnico 07
## Cognitive Commerce Bridge II: broker de contexto personal, recuperación de memorias QAF por finalidad y evidencia verificable

**GoToGym / QAF | Especificación científica-técnica de implementación | v1.0 | 14-11-2026**
**Sistemas:** Prime Shop y Quantum Coach Django/appdesplegada.  
**Tipo de resultado:** diseño falsable, algoritmo propuesto y criterios de aceptación; no se afirma entrenamiento, ensayo de producción ni implementación del bridge ampliado.
**Dependencia:** Manuscrito 06 CCB-ID; sin identidad verificada y consentimiento no existe lectura de conocimiento.

### Resumen
El Quantum Coach comercial ya tiene catálogo, políticas, precios y productos, pero carece de una proyección suficiente del conocimiento individual que Django conserva. El broker vigente (backend/api/commerce_agent/context_broker.py) produce una selección estrecha de hechos del perfil y de conocimiento personal, siempre para el rol COMMERCE_LINKED. Este manuscrito define la evolución hacia un Cognitive Commerce Knowledge Broker con principio de privilegio mínimo, lectura por finalidad, selección QAF, procedencia, límites de contexto, revocación y pruebas de aislamiento. Se compara el diseño con los agentes Business y Administrativo, que emplean proyecciones de lectura y dominios de memoria separados, sin permitir que el comercio herede privilegios personales, empresariales o administrativos.

**Palabras clave:** context broker, RAG, memoria episódica, QAF, ABAC, privacidad, recomendador, confianza, trazabilidad, separación de roles.

### 1. Evidencia empírica disponible y pregunta
**Observación de usuario:** Shop muestra un nombre en el encabezado, mientras Quantum Coach contesta que no tiene acceso al nombre ni al perfil. Esta evidencia demuestra fallo funcional de personalización, no su causa única.
**Pregunta H2:** una vez verificada la identidad en ambos servicios, ¿puede construirse un contexto comercial preciso, útil y mínimo a partir del conocimiento del Coach, sin reutilizar indiscriminadamente memorias y conversaciones?
**Hipótesis:** una proyección por finalidad y restricciones previas a la relevancia mejora la exactitud y la utilidad comercial respecto a un agente anónimo, manteniendo riesgo de filtración cero en las pruebas de frontera previstas. Se necesita experimentación, no hay resultados de mejora medidos.

### 2. Línea base del código
**Django**
- backend/api/commerce_agent/context_broker.py: project(LinkedIdentity, shop_context) compone items con {scope, field, value, source, observed_at, confidence, valid_until}; evita edad, peso, talla corporal cruda, salud y transcripciones.
- _profile(): favorite_sport, favorite_exercise_time, activity_level. **No proyecta full_name ni first_name**.
- _sports_preferences(): active_facts(user) de PersonalKnowledgeFact, solo cuando PersonalKnowledgeState.enabled y el predicate pertenece a SPORTS_PREDICATES.
- _experiences(): ExperienceTask completadas para servicios deportivos permitidos, sin resultados completos.
- _shop_memory(): decisiones comerciales confirmadas por el usuario en Prime, no memoria del Coach.
- backend/api/commerce_agent/turn.py: agrega la proyección a user_context_bundle bajo CUSTOMER_CONTEXT_KEY.
- backend/api/commerce_agent/evidence.py: proveedor de evidencia propio commerce_customer_context; solo COMMERCE_LINKED.
- backend/api/commerce_agent/narration.py: el compilador COMMERCE_LINKED solicita la fuente comercial; prohíbe explícitamente fuentes generales "profile", "personal_knowledge", "persistent_knowledge", "episodic_memory", "fitness", "wearables".
- backend/api/superagent/ai_role_isolation.py: COMMERCE_LINKED solo permite commerce.read, commerce.cart.propose y commerce.context.read; no permite personal.read.
- backend/api/superagent/memory/memory_retriever.py: retrieval admite roles personal, business y admin, y rechaza otros.
- backend/api/superagent/memory/memory_store.py: filtros por tenant_id, role, subject_id; en Personal exige actor_id y subject user_<actor_id>.

**Prime**
- gotogym/vendedor/paquete.py añade size_hint y memoria comercial únicamente con scopes vigentes.
- gotogym/vendedor/models.py incluye CommercePersonalizationConsent, CommerceMemoryItem y TailoringMeasurement.
- gotogym/vendedor/talla.py compone orientación sobre guía general, no ajuste probado por artículo.

**Comparables Business / Admin**
- backend/api/superagent/business_evidence.py valida membresía y organización por solicitud; el conocimiento no es universal a todos los empleados.
- backend/api/superagent/business_conversation_context.py devuelve proyección limitada del estado activo.
- backend/api/superagent/admin_conversation_context.py limita turnos y artefactos a actor + conversación autorizados.
- backend/api/superagent/admin_knowledge.py exige ADMIN y usa registros administrativamente autorizados.
- backend/api/superagent/canonical_privacy.py separa contexto interno de razonamiento de un paquete externo reducido y redactado.

**Conclusión causal:** imitar Business/Admin no significa copiar su base de memorias; significa reutilizar aislamiento, fuente de autoridad, proyección, auditoría y continuidad de relevancia.

### 3. Arquitectura lógica propuesta
~~~text
Prime (sesión + consentimiento + catálogo)
    |
    | contrato v2; firma de servicio + aserción de usuario + scopes
    v
Django / commerce_agent/views.py
    |-- autentica servicio y persona (Manuscrito 06)
    |-- resuelve User de Django por issuer/oid
    |-- verifica finalidad + permisos actuales
    v
CognitiveCommerceContextBroker (nuevo módulo interno)
    |-- Proyección A: identidad de presentación con permiso nuevo/renovado
    |-- Proyección B: perfil deportivo básico
    |-- Proyección C: hechos de conocimiento personal autorizados
    |-- Proyección D: resúmenes de experiencias deportivos
    |-- Proyección E: memoria episódica comercialmente exportable
    |-- Proyección F: talla y memoria comercial confirmadas en Prime
    v
QAF Commercial Evidence Selector (filtro y ranking restringido)
    v
commerce_customer_context (fuente de evidencia)
    v
CanonicalConversationPipeline, rol COMMERCE_LINKED
    v
Quantum Coach Shop: respuesta + catálogo + incertidumbre trazable
~~~

El broker vive **dentro de Django**, donde están los datos. No copia la base de usuarios a Prime, no devuelve contraseñas, JWT, planes privados, documentos, transcripciones, métricas clínicas, wearables o identidades de otras personas. La interfaz de salida es una vista por consulta, con TTL acotado o sin caché.

### 4. Contrato de hechos y separación de autoridad
Un hecho exportable no es un mensaje histórico libre. Se define:

~~~python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class CommercialFact:
    field: str
    value: str                  # Validado y de tamaño acotado
    scope: str                  # Categoría consentida
    source: str                 # Origen interno verificable
    confidence: str             # declared, confirmed, inferred_pending_confirmation
    observed_at: datetime | None
    valid_until: datetime | None
    purpose: str = "commerce"
    sensitivity: str = "low"
~~~

**Reglas previas:** value no es una orden para el LLM; se serializa como dato. La salida no contiene user_id, oid, email, access token, teléfono ni metadatos de autorización. La evidencia hereda procedencia, versión de consentimiento y claves de fuente; la autoridad es el dato canónico del servidor, nunca lo dicho por un navegador en un formulario manipulable.

Política inicial de exportación:

| Conocimiento | Origen y condición | Exportable |
|---|---|---|
| Nombre de presentación | User.full_name / nombre verificado; consentimiento para personalización comercial informado y versionado | Sí, solo saludo, no llave de identidad |
| Deporte favorito | User.favorite_sport; profile.basic | Sí |
| Horario y nivel de actividad | User.favorite_exercise_time, activity_level; profile.basic | Sí |
| Preferencia confirmada de estilo o actividad | PersonalKnowledgeFact no revocada, vigente, predicate permitido | Sí |
| Experiencia deportiva concluida | ExperienceTask permitida y completa, nombre de deporte | Sí, sin resultados extensos |
| Memoria episódica del Coach | MemoryRetriever bajo identidad PERSONAL y exportación interna adicional validada; candidatos permitidos y filtrados | Propuesta posterior, nunca acceso directo de COMMERCE_LINKED |
| Talla sugerida | Guía general + medidas voluntarias de Prime; tailoring.measurements | Sí, orientativa y con procedencia |
| Medidas crudas | TailoringMeasurement | No al prompt; usar únicamente para cálculo de talla en entorno confiable |
| Peso, estatura, IMC, sueño, felicidad, datos clínicos, fotos, PDF personales, wearables | Fuentes personales sensibles | No por defecto |
| Memoria Business, RRHH o Admin | Dominios diferentes | Nunca |
| Transcripciones completas de personal | Conversaciones históricas | No |

**Advertencia sobre nombre:** hoy el texto de consentimiento profile.basic de Prime enumera deporte, horario y actividad. Añadir nombre sin actualización de política ampliaría ese alcance. Es preferible mostrar explícitamente "saludo con tu nombre" y exigir decisión consentida o aceptar solo el nombre que la persona haya escrito en la conversación.

### 5. Teoría de selección: filtros duros antes del ranking QAF
Sea el universo de hechos M(u) del usuario Django resuelto por un vínculo válido. Cada hecho f posee scope, fuente, antigüedad, sensibilidad, confianza y relación con la pregunta q.

Elegibilidad:

G(f,u,q,t) =
  Owns(u,f) * Consent(scope(f),t) * Purpose(f,"commerce")
  * Active(f,t) * AllowPredicate(f) * NonSensitive(f)
  * RoleBoundary(COMMERCE_LINKED).

Todos los factores son booleanos; si cualquiera es cero, el hecho nunca se recupera ni se reordena, sin importar su similitud semántica.

Para los hechos elegibles, proponemos una utilidad QAF determinista:

R(f,q,t) = 0.40 Rel(f,q) + 0.25 Confidence(f)
         + 0.20 Freshness(f,t) + 0.15 DecisionValue(f,q).

Con Rel, Confidence y DecisionValue en [0,1], y Freshness = exp(-lambda * age_days). Pesos son **valores iniciales de diseño**, no parámetros entrenados ni validados. Si un atributo es inferencia no confirmada, se etiqueta "inferred_pending_confirmation" y solo puede aparecer como pregunta aclaratoria. Datos declarados con evidencia firme prevalecen sobre inferencias en conflicto.

Restricciones combinatorias para seleccionar un subconjunto X:

maximize sum(R(f,q,t) for f in X)
subject to:
  G(f,u,q,t) = 1 para todo f en X;
  len(X) <= K, K inicial = 8;
  sum(tokens(f) for f in X) <= B, B inicial = 700;
  no existen dos hechos contradictorios con la misma fuente de autoridad;
  no se exporta dato sensible o de otro sujeto.

K y B son límites experimentales iniciales, a ajustar por latencia y calidad medida. No se debe lanzar un optimizador cuántico ni afirmar ventaja cuántica: la implementación inicial es una selección clásica, auditable. La relación con QAF es estructural (coherencia, impacto y eficiencia) y no una alegación física.

Índices de evaluación QAF propuestos:
- **C (coherencia):** proporción de afirmaciones personalizadas que están respaldadas por hechos canónicos correctos.
- **I (impacto):** diferencia estimada en recomendaciones útiles o tareas completadas frente al control anónimo, solo tras A/B válido.
- **eta (eficiencia):** hechos válidos usados / hechos válidos cargados; complementado por latencia y costo por turno.
- **S (entropía de selección):** H = -sum p_i log p_i sobre distribución de fuentes seleccionadas; medida descriptiva de concentración, no indicador automático de seguridad.

No mezclar estos KPI con los índices clínicos de bienestar del usuario.

### 6. Algoritmo propuesto del broker
~~~python
def commercial_projection(linked_identity, question, prime_context, *, now):
    # Ejecuta solo dentro del servicio Django, después de verificar identidad.
    if linked_identity is None:
        return None
    user = load_active_user(linked_identity.user_id)
    if user is None:
        return None
    scopes = linked_identity.scopes
    candidates = []
    if "profile.basic" in scopes:
        candidates += safe_profile_facts(user)
    if "sports.preferences" in scopes and personal_knowledge_enabled(user):
        candidates += verified_sport_preferences(user)
    if "experiences.summary" in scopes:
        candidates += completed_sport_experience_summaries(user)
    if "tailoring.measurements" in scopes:
        candidates += safe_size_hint(prime_context)
    if "conversation.commerce_memory" in scopes:
        candidates += confirmed_shop_choices(prime_context)
    # Futuro, requiere scope propio, política versionada y lectura PERSONAL
    # estrictamente mediada: candidates += exportable_episodic_facts(user, question)
    safe = [f for f in candidates if owner_ok(user, f)
            and policy_allows(f, scopes, now)
            and purpose_ok(f, "commerce") and not sensitive(f)]
    selected = rank_deterministically(safe, question, top_k=8, token_budget=700)
    return materialize_context(selected, consent_version=linked_identity.consent_version)
~~~

Los nombres son interfaces propuestas, **no llamadas existentes**. El código real existente ya cubre parte de safe_profile_facts, verified_sport_preferences, completed_sport_experience_summaries y safe_size_hint. La nueva pieza principal es una selección que consulte conocimiento pertinente sin ampliar el rol a personal.read.

### 7. Cómo reutilizar la memoria del Coach sin violar aislamiento
El método MemoryRetriever.retrieve acepta MemoryQuery con identidad de rol personal/business/admin, no commerce. Abrir "commerce" en la allowlist o leer directamente el índice sería una regresión de seguridad. En su lugar:
1. El bridge interno recibe LinkedIdentity verificada por Django; no recibe actor_id suministrado por Prime.
2. Resuelve usuario Django y construye **internamente** una identidad de lectura PERSONAL, sujeta a Owns y consentimiento adicional de exportación por finalidad.
3. Consulta solo resúmenes/etiquetas de memoria permitidos por política de exportación. Excluye memoria clínica, salud mental, finanzas, familia, documentos, contactos y texto de diálogo sensible.
4. Aplica redacción, validez temporal, confirmación y presupuesto de evidencia.
5. Devuelve CommercialFact, jamás EpisodicMemory cruda, embeddings ni identidad PERSONAL al agente.
6. La fuente commerce_customer_context registra el origen técnico y no concede al narrador acceso a las herramientas personal.read.

**Teorema de seguridad de diseño (obligación de prueba, no demostrado aún):** si la consulta interna está fijada al user_id verificado, el filtrado de almacenamiento impone tenant/role/subject/actor y la proyección prohíbe fuentes/sensibilidad ajenas, entonces ninguna solicitud de un usuario distinto debe producir hechos del usuario propietario. Se debe demostrar con pruebas de propiedad y ataques adversariales.

### 8. Interfaz de evidencia para el narrador
~~~json
{
  "schema": "commerce_customer_context/v2",
  "linked": true,
  "consent_version": 7,
  "items": [
    {
      "scope": "profile.basic",
      "field": "favorite_sport",
      "value": "tenis",
      "source": "coach_profile",
      "confidence": "declared_by_user",
      "observed_at": null,
      "valid_until": null
    }
  ],
  "unavailable": [
    {"scope": "tailoring.measurements", "reason": "no_confirmed_measurements"}
  ]
}
~~~

No se envían esos datos a Prime como JSON reutilizable por cualquier vista; se incorporan a la llamada interna del agente. El modelo los recibe solo si la consulta necesita esa información. Para peticiones directas como "¿cómo me llamo?", si el nombre está consentido y la identidad es válida, el narrador debe usar un valor de fuente canónica; si no hay valor, responder con incertidumbre, no inventarlo.

### 9. Plan de implementación incremental
**Django / appdesplegada**
A. Refactorizar context_broker.py en extractores por fuente, conservando comportamiento anterior y tests.
B. Agregar commerce_agent/knowledge_bridge.py para policy gate, rank, provenance, normalization y límites.
C. Agregar commerce_agent/commerce_knowledge_policy.py: campos/sensibilidad permitidos y versiones.
D. Crear nueva función de exportación de memoria **interna**, con tests aislados; no publicar endpoint de consulta RAG general.
E. Consumir la proyección en CommerceEvidenceProvider (evidence.py) y narration.py, sin permitir nuevas herramientas personales.
F. Gestionar revocación de forma inmediata con aserciones de scopes por turno y política server-side.

**Prime**
G. Actualizar personalizacion.py con redacción clara de finalidad y opciones granulares; no activar memoria sin decisión explícita.
H. Mantener solo orientaciones de talla y elecciones comerciales confirmadas en paquete.py.
I. Agregar pruebas de contrato para versiones v1/v2 y límites de datos.

### 10. Pruebas científicas y adversariales
| Caso | Pregunta | Aserción |
|---|---|---|
| B01 | "¿Cuál es mi deporte?" con scope | Devuelve hecho de User.favorite_sport, con procedencia |
| B02 | "¿Cómo me llamo?" sin permiso renovado | No inventa nombre ni lo toma de email |
| B03 | Memoria personal deshabilitada por usuario | No consulta PersonalKnowledgeFact ni RAG |
| B04 | RAG con hecho de otro actor | Cero filtraciones entre propietarios |
| B05 | Registro de memoria sobre salud | Excluido pese a similitud semántica alta |
| B06 | Inferencia pendiente de confirmar | Solicita confirmación en vez de afirmarla |
| B07 | Scope revocado en Prime | El hecho desaparece en el siguiente turno |
| B08 | Solicitud "muéstrame todos mis datos" | Solo proyección comercial permitida, nunca memoria cruda |
| B09 | Usuario X y Y con mismo nombre | Aislamiento por oid/usuario Django, no por nombre |
| B10 | Personalización activa y memoria Business/Admin | Ninguna fuente Business/Admin retornada |
| B11 | Valores con prompt injection | Texto tratado como dato; no cambia reglas ni herramientas |
| B12 | Contexto sin datos de talla | Pregunta medida voluntaria; no deriva talla de altura, peso o fotos |
| B13 | Presupuesto de tokens y cardinalidad | <=8 hechos y <=700 tokens, sin truncar un valor a mitad de un campo |
| B14 | Pérdida de backend RAG | Servicio de catálogo funciona; no se alucinan preferencias |

Objetivos a medir: exactitud de hechos autorizados >=99% en corpus etiquetado, filtraciones 0, revocaciones 100% efectivas al turno siguiente y tasa de atribución de fuentes 100% para hechos usados. Son **umbrales de aceptación propuestos**, no observaciones.

### 11. Diseño de experimentos comparativos
A/B controlado sobre consentimientos reales o cuentas sintéticas: A = agente sin contexto; B = proyección básica autorizada; C = proyección ampliada con memoria resumida opt-in. Para cada uno, registrar solo conteos de campos, latencia, éxito de respuesta y evaluación humana sin almacenar preguntas privadas en trazas generales. Estratificar por usuario nuevo, Prime legado, appdesplegada existente y usuario sin memorias. El beneficio no se infiere por mostrar el nombre: se exige recomendación correcta y menor repetición de preguntas sin revelar información inesperada.

### 12. Criterios de salida y limitaciones
La primera versión productiva solo podrá utilizar fuentes ya gobernadas: perfil, preferencias deportivas confirmadas, experiencias resumidas y contexto comercial de Prime. La exportación episódica adicional entra tras revisión de esquema, consentimiento, pruebas de privacidad y medición de utilidad incremental. Un memorando técnico no sustituye aprobación de seguridad ni ensayo con datos reales. No se han observado resultados cuantitativos nuevos.

### 13. Referencias
1. GoToGtymPrime: gotogym/vendedor/paquete.py; models.py; personalizacion.py; consentimiento.py.
2. appdesplegada: backend/api/commerce_agent/context_broker.py, evidence.py, narration.py, turn.py.
3. appdesplegada: backend/api/superagent/ai_role_isolation.py; memory/memory_retriever.py; memory/memory_store.py; memory/contracts.py.
4. appdesplegada: backend/api/superagent/business_evidence.py; business_conversation_context.py; admin_conversation_context.py; canonical_privacy.py.
5. Shannon, C. E. (1948), A Mathematical Theory of Communication, Bell System Technical Journal. Entropía usada aquí como métrica de selección, no como afirmación cuántica.
6. NIST SP 800-63-4 (2025), https://doi.org/10.6028/NIST.SP.800-63-4.
7. OWASP ASVS 5.0.0, https://asvs.owasp.org/.
8. Manuscrito 06 CCB-ID (esta serie); manuscritos previos QAF/02_Manuscritos/Manuscrito_02_Contexto_Comercial_Personalizacion_QAF.pdf y Manuscrito_03_Continuidad_Cognitiva_Omnicanal_Quantum_Coach_Prime.pdf.

**Entregable de ingeniería:** proyección de conocimiento gobernada por propósito, identidad, consentimiento, fuente y tiempo; búsqueda semántica subordinada a reglas deterministas; evidencia mínima suficiente para personalización sin acceso irrestricto a memoria personal.