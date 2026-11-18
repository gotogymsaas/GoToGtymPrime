# Manuscrito científico-técnico 19 — Cognitive Commerce Bridge
## Validación end-to-end de usuarios registrados y nivel real de personalización

**GoToGym / Friends N Gifts S.A.S. | 14 noviembre 2026.**
**Naturaleza:** protocolo experimental reproducible; no son resultados de pruebas de producción ejecutadas.

### Resumen
Este manuscrito define el proceso de aceptación end-to-end desde la sesión APP existente hasta la respuesta comercial, consulta de experiencias y acción validada de tienda. La meta no es solamente saber el nombre: se mide la profundidad factual del contexto autorizado y la incertidumbre de tallaje, sin compartir resultados clínicos o imágenes. Un CI verde no demuestra por sí solo que la producción resuelva la identidad, haya aplicado migraciones ni use correctamente la memoria.

### 1. Evidencia de origen
La APP conserva identidad OIDC, ExperienceTask y perfiles de deportes; Prime tiene su propia sesión, consentimiento y medidas confirmadas. Los PR de Cognitive Commerce Bridge conectan una aserción por turno con un Context Broker consentido. En una conversación de prueba humana el Coach reconoció el nombre y el tenis, pero pidió medidas para tallaje. Este resultado corresponde a personalización básica, no a conocimiento total.

### 2. Niveles de capacidad verificable
- C0: modo anónimo, conversación y catálogo útil.
- C1: identidad federada, nombre correcto con autorización.
- C2: deporte favorito, horario y preferencias confirmadas.
- C3: estados de experiencias y preferencias de entrenamiento, cada categoría con permiso.
- C4: talla orientada por evidencia de medidas vigentes y guía general/específica explícita.
- C5: continuidad cognitiva omnicanal, revocación correcta, reentrada opcional a APP y acciones comerciales verificadas.

~~~text
Truthfulness = personal_claims_with_verified_source / all_personal_claims
Coverage = relevant_authorized_facts_used / relevant_authorized_facts_available
CrossUserLeak = leaked_facts_A_to_B / tested_cross_user_cases
Release = CI_green AND migrations_applied AND serving_sha_verified
          AND same_oidc_principal AND valid_scopes AND E2E_success
          AND CrossUserLeak == 0
~~~
Los indicadores QAF C, I y eta miden coherencia, impacto y eficiencia. Ningún beneficio económico compensa un acceso no autorizado.

### 3. Recorrido de prueba
1. En APP, entrar con cuenta existente y confirmar que continúan perfil, planes e historial.
2. Abrir Shop con la misma identidad OIDC, sin nueva contraseña ni cuenta.
3. Consultar estado de Prime; verificar enlace y consentimientos, sin exponer token ni oid al navegador.
4. Saludar al Coach y preguntar el nombre; comparar con perfil canónico autorizado de Django.
5. Preguntar deporte y preferencia; verificar el campo y su procedencia, o abstención honesta.
6. Conceder opt-in independiente para experiencias; consultar Exp012/013/006 completadas. Sólo completitud, sin resultados ni fotos.
7. Solicitar camiseta para tenis y talla; el sistema consulta guía y medidas vigentes si existe permiso.
8. Si falta medición, el Coach puede sugerir voluntariamente una experiencia educativa en APP y pedir medidas con cinta para ajuste; jamás inferir centímetros de la cámara.
9. Revocar consentimiento; la respuesta siguiente no puede incluir hechos de ese scope.
10. Cerrar sesión y entrar con segundo usuario; el historial y el contexto no se mezclan.

### 4. Matriz completa de regresión de 24 casos
P01 Inicio OIDC sin loop. P02 Cuenta Django existente intacta. P03 Cuenta Prime intacta. P04 Emisor y oid concordantes. P05 HMAC de servicio válido. P06 HMAC de persona distinto y válido. P07 Replay jti denegado. P08 Sin consentimiento, anónimo. P09 Nombre correcto. P10 Deporte correcto. P11 Preferencias verificadas. P12 Inferencia pendiente exige confirmar. P13 Exp012 completada expone sólo estado. P14 Exp013 waiting_input no significa completada. P15 Exp006 no diagnostica. P16 Sin scope no se consulta ExperienceTask. P17 Medidas vigentes y fuente de talla. P18 Sólo peso/altura: abstenerse. P19 CTA a APP segura. P20 Revocación en siguiente turno. P21 Usuario A→B, cero cruce. P22 Precio/stock de producto verdadero. P23 Compra general sin personalización. P24 Caída temporal de Django/Redis deja atención segura.

### 5. Algoritmo de aceptación de ingeniería
~~~python
def evaluate_real_user_safely(user_A, user_B, shop, coach):
    assert verified_link(user_A, shop, coach, by=("issuer", "oid"))
    assert session_user_and_authorized_name_correct(user_A)
    assert no_raw_experience_results_in_commerce_response(user_A)
    assert size_claims_have_valid_measurement_provenance(user_A)
    revoke_optional_scope(user_A, "experiences.commerce_guidance")
    assert next_turn_has_no_revoked_scope_data(user_A)
    assert no_cross_user_content_after_logout_login(user_A, user_B)
    assert public_catalog_still_available_without_optional_consent()
~~~
Es pseudocódigo; el runner productivo exige una identidad de prueba autorizada, instrumentación no invasiva y verificación de SHA servido. No ejecutar con credenciales enviadas por chat.

### 6. Ensayo humano, análisis y medición
Registrar C0–C5 logrado, claims con fuente, latencia P95, preguntas repetidas, tasa de oferta de CTA aceptada, incertidumbre de talla, conversión y CSAT. Comparar grupos con consentimiento voluntario y reportar tamaños de muestra e intervalos de confianza. Una persona que rechaza opt-in debe poder consultar la tienda y comprar.

### 7. Control de release y rollback
Antes de declarar end-to-end completo, demostrar migración 0005 de Prime en PostgreSQL, coincidencia de scope entre APP y Prime, SHA desplegado en ambos servicios, CI general verde, permisos reales y prueba humana en shop.gotogym.store. Cualquier fallo de aislamiento exige rollback de la función de contexto, nunca borrar cuentas o planes. El sistema anónimo y carrito deben seguir operativos.

### 8. Limitaciones
El valor de una experiencia de postura no mide antropometría real; la comprobación de completitud no prueba qué se concluyó ni sustituye ajuste en taller. Un pronóstico de utilidad no equivale a resultado experimental. Estos 24 escenarios se documentan como protocolo pendiente de ejecución productiva.

### 9. Fuentes
GoToGtymPrime vendedor y Django commerce_agent; manuscritos QAF 06–18; ISO 8559-1:2017 https://www.iso.org/standard/61686.html y MediaPipe Pose Landmarker https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker.
