# Manuscrito científico-jurídico 09 — Cognitive Commerce Bridge
## Gobernanza legal interoperable, automatización de autorizaciones y experiencia sin fricción

**GoToGym / Friends N Gifts S.A.S.** | Versión de investigación **1.1** | 14 de noviembre de 2026 | Colombia.  
**Repositorios auditados:** \`gotogymsaas/appdesplegada\` y \`gotogymsaas/GoToGtymPrime\`.  
**Naturaleza:** propuesta de investigación jurídica y de ingeniería de procesos. **No constituye asesoría jurídica vinculante ni política publicada**. Requiere revisión y aprobación de asesor jurídico colombiano, responsable de protección de datos y dueño del proceso antes de activar en producción.

### Resumen

La identidad universal y el Cognitive Commerce Bridge ya permiten reconocer a un usuario de GoToGym Shop, pero los procesos de aceptación contractual y consentimiento de tratamiento de datos están fragmentados entre APP y Prime. Se propone un **Sistema de Gobierno de Autorizaciones del Ecosistema (SGAE)** que permite reutilizar de manera segura una decisión previa **solo cuando hay evidencia, identidad, finalidad, ámbito, texto y versión equivalentes**, sin obligar a repetir pantallas y sin convertir el contrato en consentimiento general para tratamiento secundario. Incluye contrato marco del ecosistema, anexos propios de APP y Shop, avisos de privacidad, autorización granular, estado y revocación interoperables, trazabilidad y orquestación de decisiones. El agente comercial no recibe memorias personales crudas ni datos sensibles por defecto. La hipótesis de menor fricción y mejor conversión debe ensayarse; no se presenta como resultado demostrado.

**Palabras clave:** Ley 1581, Ley 1480, Ley 2439, Corte Constitucional C-192 de 2026, Decreto 1074, identidad federada, BPMN, autorización por finalidad, responsabilidad demostrada, minimización, IA y automatización.

### 1. Problema, evidencia y límites

**Problema de ingeniería empresarial.** Un cliente puede iniciar sesión en APP, volver a autenticarse en Shop, ver otra pantalla contractual, vincular su cuenta, buscar ajustes de consentimiento y activar scopes individualmente antes de obtener atención personalizada. Varios pasos son legítimos pero se pueden hacer contextuales y no repetitivos. La solución no es eliminar autorizaciones sino **automatizar la decisión de si hay que solicitarlas**.

Fuentes del código:
- \`appdesplegada/frontend/pages/auth/Terminos_y_Condiciones_2026-10-05.md\`: sección 8.1 exige habilitación separada de memoria personal y adición 15 trata identidad universal sin conceder por sí sola circulación cruzada.
- \`appdesplegada/frontend/pages/info/PoliticaPrivacidad.html\`: describe datos de perfil, bienestar, wearables y consentimiento de canales.
- \`GoToGtymPrime/gotogym/accounts/templates/accounts/terms_and_conditions.html\`: condiciones de tienda de octubre de 2026, parcialmente desactualizadas frente al ecosistema.
- \`GoToGtymPrime/gotogym/accounts/templates/accounts/accept_terms.html\`: aceptación contractual específica tras el login.
- \`GoToGtymPrime/gotogym/gotogym/templates/static_pages/politicas_privacidad_usuario.html\`: titula Quantum Coach y fecha agosto en superficie Shop.
- \`GoToGtymPrime/gotogym/vendedor/models.py\`, \`consentimiento.py\`, \`personalizacion.py\`: scopes de personalización explícitos, auditables y revocables.
- \`appdesplegada/backend/api/commerce_agent/context_broker.py\`: ya separa campos de perfil autorizados de salud, memoria privada y datos clínicos.

**Pregunta:** ¿cómo reducir pasos de acceso y atención, conservando voluntad válida, prueba de consentimiento, derechos del consumidor y continuidad por finalidad?

Hipótesis: una capa de autorización interoperable y contrato marco versionado puede reducir repetición sin ampliar la superficie de datos. Se probará con clientes sintéticos y canario humano, comparando número de pasos, tiempo hasta primera recomendación útil, tasa de revocación efectiva, comprensión de la finalidad y filtraciones entre roles.

### 2. Normativa colombiana y actualización de jurisprudencia

- **Ley Estatutaria 1581 de 2012**: principios de finalidad, libertad, acceso restringido, seguridad y derechos del titular; autorización previa e informada salvo excepciones legales; reglas reforzadas para datos sensibles. No usar una aceptación general para presumir memoria comercial, salud o publicidad.
- **Decreto 1377 de 2013, incorporado al Decreto 1074 de 2015**: autorización demostrable por escrito, voz o conducta inequívoca; **el silencio no constituye autorización**. En datos sensibles informar su carácter voluntario y obtener autorización expresa cuando corresponda.
- **SIC Circular Externa 002 de 2024**: responsabilidad demostrada y transparencia en el tratamiento de datos personales mediante IA; evaluación de necesidad, proporcionalidad y seguridad.
- **Ley 1480 de 2011, arts. 47, 50, 51**, y **Ley 2439 de 2024**: derechos de consumidor, comercio electrónico, transparencia de ofertas, retracto y reversión de pago. La Ley 2439 modificó el máximo de devolución por retracto en comercio electrónico a **15 días calendario**, después de cumplir los requisitos legalmente aplicables.
- **Sentencia C-192 de 2026, Corte Constitucional**: declaró exequible la expresión «En los casos de comercio electrónico» bajo el entendimiento de que el plazo máximo de quince días calendario para la devolución por retracto se aplica **uniformemente a las modalidades de contratación del art. 47 de la Ley 1480**. Por tanto, el análisis legal anterior, limitado a comercio electrónico, debe leerse actualizado según esta sentencia. El texto comercial debe ser revisado por asesoría jurídica.
- **Ley 527 de 1999**: mensajes de datos y evidencia de aceptación electrónica.
- **Ley 2300 de 2023**: obligaciones y límites para gestión de comunicaciones con consumidores; no confundir mensajes transaccionales indispensables con mercadeo.
- Reglas especiales para niñas, niños y adolescentes, titulares de datos sensibles, transmisiones internacionales, atención de peticiones y derechos de supresión, rectificación y revocación.

Referencias oficiales: https://www1.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=257116 ; https://www.corteconstitucional.gov.co/relatoria/2026/c-192-26.htm ; https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php/norma.php?i=53646 ; https://sedeelectronica.sic.gov.co/sites/default/files/publicaciones/Concepto_Tratamiento.pdf .

### 3. Arquitectura propuesta: SGAE

~~~text
Microsoft Entra External ID -- sesión / vínculo OIDC --> Prime y Django
                                                      |
                                  Policy Resolver / SGAE
                     /                  |                    \
             Marco contractual      Finalidades          Evidencia y auditoría
             + anexos por APP     por categoría           inmutable por evento
                     \                  |                    /
                          Decision API segura
                     aceptado | requiere informar | denegado
                                   |
                    Cognitive Commerce Bridge (Django)
                         prueba + scopes + minimización
                                   |
                  Quantum Coach Shop: contexto comercial permitido
~~~

No crear un repositorio libre de memorias. El **registro de autorizaciones no sustituye la identidad**: valida propósito y versiones después de resolver \`issuer + oid\`. La autoridad de datos personales permanece en Django; las decisiones de Shop pueden conservarse localmente y sincronizarse únicamente tras una equivalencia probada de finalidad y autoridad. Si no existe prueba suficiente, preguntar en el momento pertinente.

### 4. Modelo jurídico de decisión y reglas de negocio

Sea U la identidad federada autenticada, P una finalidad, D una categoría de dato, R un recurso o superficie, V una versión de aviso, y T el instante. Se propone:

\`Reuse(U,P,D,R,V,T) = VerifiedLink(U) AND ValidEvidence(U,P,D,V,T) AND EquivalentPurpose(P,R) AND NotRevoked(U,P,T) AND NotExpired(U,P,T) AND PolicyCompatible(V)\`.

La regla no sustituye un análisis jurídico de bases de legitimación en cada finalidad. \`Reuse=false\` implica preguntar o mantener modo general, **nunca inventar un consentimiento**.

**Separación operativa obligatoria:**
1. **Identidad:** reconocer al cliente una sola vez mediante sesión OIDC y vinculación verificada.
2. **Contrato:** aceptar términos de la operación correspondiente, con alcance y versión.
3. **Tratamiento necesario:** prestar servicio, pedidos, fraude y cumplimiento legal bajo base aplicable y avisos claros.
4. **Personalización comercial opcional:** fines y categorías diferenciados, denegación sin impedir compra general.
5. **Datos sensibles/salud:** finalidad explícita, voluntariedad y controles separados; excluir de comercio por defecto.
6. **Marketing y canales:** finalidades de comunicación separadas de transacciones y Coach.
7. **Memoria personal:** su habilitación en APP nunca se convierte por sí sola en consentimiento de exportación a Shop.

### 5. Modelo de datos y automatización

Entidad propuesta \`EcosystemAuthorizationDecision\`:
\`decision_id, actor_ref, issuer, purpose_code, data_category, product_scope, allowed, notice_version, notice_hash, legal_basis_code, source_surface, captured_at, expires_at, revoked_at, proof_ref, decision_seq\`.

\`actor_ref\` y \`issuer\` se verifican en servidor; nunca aceptar un actor declarado por el navegador. Registrar una secuencia append-only de otorgamiento/revocación para proteger trazabilidad, idempotencia y concurrencia. Los cambios deben ser reversibles y sin sobrescribir decisiones previas. Los permisos comerciales actuales \`CommercePersonalizationConsent\` continúan como compatibilidad local mientras se valida equivalencia.

**Algoritmo conservador:**
~~~python
def resolve_experience(*, linked, document_version, purchase_terms, purpose, proof):
    if not linked:
        return "LINK_REQUIRED"
    if purchase_terms.must_accept(document_version):
        return "CONTRACT_UPDATE_REQUIRED"
    if purpose.is_optional:
        if not proof or not proof.valid_for(purpose):
            return "OPTIONAL_PERMISSION_PROMPT"
        if proof.revoked or proof.expired:
            return "OPTIONAL_PERMISSION_PROMPT"
    return "READY"
~~~
El servicio general se mantiene operativo si el permiso opcional se rechaza. La interfaz **no bloquea pago ni catálogo por falta de marketing o personalización**.

### 6. Diseño BPM y experiencia del cliente

**Antes:** autenticación APP → autenticación Shop → aceptar condiciones generales Shop → confirmar vínculo → abrir ajustes → activar nombre → activar perfil → activar experiencias → volver a chat → iniciar nueva conversación → compra.

**Propuesto:** sesión universal válida → resolución contractual automática por versión → conversación general inmediata → autorización contextual opcional una vez, si hace falta → consulta mínima de Django → recomendación y compra. No volver a solicitar permiso ya vigente y equivalente; presentar en Mi cuenta un panel único para consulta, modificación y revocación.

BPMN conceptual con compuertas:
\`Inicio > sesión? > vinculación? > contrato aplicable vigente? > finalidad opcional? > prueba válida? > permitir/proponer > compra\`.
Al rechazar permiso opcional: \`chat_general + catálogo + checkout\`.

### 7. Borradores de cláusulas contractuales (no publicados)

**7.1 Identidad común.** «GoToGym podrá ofrecer un acceso unificado para los servicios del ecosistema. La autenticación común no implica suscripción compartida ni habilita acceso indiscriminado al perfil o memorias de los usuarios. La vinculación de cuentas se realizará mediante verificaciones seguras y no solo por coincidencia de correo».

**7.2 Continuidad de atención.** «Cuando el titular haya autorizado finalidades y categorías apropiadas, GoToGym podrá utilizar hechos mínimos y pertinentes de su perfil verificado para mantener continuidad entre sus experiencias de Quantum Coach y Shop. Los hechos se seleccionarán según la pregunta y no se transferirán conversaciones completas al vendedor».

**7.3 Personalización voluntaria.** «Podrás permitir o rechazar la consulta de nombre, preferencias, experiencias y medidas para personalización comercial. Rechazar estas opciones no impide el acceso a la tienda ni la compra general. Tus decisiones se podrán consultar o modificar desde Mi cuenta».

**7.4 Medidas corporales.** «Las medidas que decidas suministrar para confección o tallaje se tratarán para esa finalidad. El sistema podrá calcular una orientación de talla; el resultado depende de la guía disponible y la exactitud de las medidas. No se tomarán datos clínicos o de dispositivos para venta sin la autorización específica que exija la ley».

**7.5 Memoria personal y empresarial.** «La memoria de Quantum Coach y los datos tratados por Business y Administración tienen controles propios. La autenticación no permite que Shop los consulte automáticamente; únicamente se proyectarán hechos para finalidades autorizadas y bajo límites técnicos de acceso».

**7.6 Control y seguridad.** «Podrás conocer, actualizar y rectificar tus datos, pedir prueba de autorizaciones y solicitar revocación o supresión cuando proceda, por los canales de privacidad informados. GoToGym conservará los registros estrictamente necesarios por obligaciones legales y seguridad».

**7.7 Información y atención automatizada.** «Quantum Coach es un agente automatizado. Sus recomendaciones son orientativas, podrán contener errores y no sustituyen atención profesional o médica; podrás solicitar soporte humano y consultar condiciones reales de precio, existencias, garantía, retracto y devolución antes de comprar».

**7.8 Retracto y reembolso.** «Se reconocerán los derechos legales de retracto y reembolso en las modalidades y términos aplicables. El reembolso por retracto respetará el límite de quince días calendario y las condiciones previstas por la normativa y la interpretación constitucional vigentes. Esta cláusula no restringe derechos legales».

### 8. Gobierno de cambios y compatibilidad

- No publicar un contrato actualizado solo porque el archivo esté en \`main\`. Usar versiones aprobadas, firma de revisión jurídica, hash de contenido y fecha efectiva.
- No otorgar permisos retroactivos a registros sin evidencia equivalente. Las decisiones previas se conservan sin alteraciones destructivas.
- El estado de consentimiento comercial puede conservarse en Prime temporalmente, pero todo acceso de Django debe estar condicionado a un vínculo y aserción verificados.
- Prohibido trasladar la memoria Business/Admin o clínica al vendedor mediante un consentimiento genérico.
- Registrar hechos de cumplimiento sin almacenar mensajes privados, secretos, prompts, fotos ni historia médica en logs.
- Políticas en ambos repositorios deben tener el mismo identificador semántico de finalidad, no necesariamente idéntico alcance de producto.

### 9. Programa de manuscritos técnicos de implementación posteriores

| Manuscrito | Entregable | Repositorio |
|---|---|---|
| **10 — Catálogo legal versionado y gobierno** | Contract registry, hashes, anexos, responsable de aprobación, auditoría de cambios | Ambos |
| **11 — SGAE y Decision API** | Autorización por finalidad, compatibilidad, revocación y contratos de API | Django + adaptador Prime |
| **12 — BPMN y automatización de procesos** | Orquestación de onboarding, login, aceptación, identidad y checkout sin fricción | Ambos |
| **13 — Context Broker comercial de datos autorizados** | Selector por consulta, protección de salud, talla y memoria permitida | Django |
| **14 — Derechos del titular y operaciones de privacidad** | Consulta, rectificación, revocación, supresión y evidencia interoperable | Ambos |
| **15 — Seguridad y cumplimiento automático** | Pruebas de aislamiento, policy-as-code, alertas, SAST, trazabilidad | Ambos |
| **16 — Evaluación científica de experiencia** | Métricas QAF, ensayos A/B, accesibilidad, auditabilidad, no coerción | Ambos |

El manuscrito 09 establece el diseño jurídico y de negocio; los documentos 10–16 deben volverse PR independientes con tests, canario y revisión jurídica.

### 10. Pruebas de aceptación antes de producción

**J01:** mismo usuario sin cambios de finalidad no repite autorización válida. **J02:** usuario sin consentimiento no es personalizado. **J03:** usuario revoca: siguiente turno no usa datos revocados. **J04:** aceptación de términos no autoriza memoria ni marketing. **J05:** cuenta antigua no recibe permisos retroactivos. **J06:** menor o dato sensible no pasa al vendedor. **J07:** dos usuarios en un navegador mantienen separadas sus decisiones. **J08:** documentos tienen versión, hash, historial y aprobación. **J09:** compra/checkout no exige personalización. **J10:** textos de retracto y devolución ajustados al derecho vigente y resolución jurídica. **J11:** interfaz APP/Prime no contradice los mismos propósitos. **J12:** auditoría de consentimiento no expone datos personales en logs.

Objetivos experimentales iniciales, no resultados: fricción (pasos de onboarding) menor que control; comprensibilidad de permisos >=90% en prueba humana; falsas autorizaciones = 0; filtraciones de roles = 0; cancelación de permisos efectiva al siguiente turno.

### 11. Plan de liberación

**Fase A — inmediata y no invasiva:** publicar manuscrito en QAF, archivo machine-readable de obligaciones por superficie, analizador estático de drift y suite de pruebas. No cambiar políticas publicadas.
**Fase B — aprobación:** revisión por asesor legal colombiano (incluida C-192/2026), responsables y encargados, textos contractuales y pantallas.
**Fase C — implementación aditiva:** decisión API versionada, compatibilidad con consentimiento, registro de evidencias, UI contextual, revocación.
**Fase D — validación E2E:** pruebas de dos cuentas, canario, accesibilidad, retracto, compra y soporte humano.
**Fase E — publicación gradual:** fechas efectivas, aceptación conforme a finalidad, alertas y rollback sin pérdida de cuentas/planes.

### 12. Conclusión
La optimización jurídica no debe medirse por cuántas autorizaciones se ocultan, sino por cuántos pasos verdaderamente redundantes se eliminan conservando prueba, libertad, reversibilidad y claridad para el cliente. Un sistema de Gobierno de Autorizaciones del Ecosistema convierte la interoperabilidad en un servicio auditable y seguro, en lugar de convertir al vendedor en titular de todas las memorias del usuario.

**Fuentes normativas y técnicas:** Ley 1581/2012, Decreto 1377/2013 y Decreto 1074/2015, Ley 1480/2011, Ley 2439/2024, Sentencia C-192/2026, Ley 527/1999, Ley 2300/2023, SIC Circular Externa 002/2024; archivos nombrados en los apartados 1 y 2. El contenido representa una revisión técnica-jurídica y no reemplaza el dictamen legal específico de Friends N Gifts S.A.S.