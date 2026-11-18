# Cognitive Commerce Bridge - índice de la serie de implementación (2026)

**Proyecto:** Quantum Coach Shop + appdesplegada; 14 de noviembre de 2026.  
**Revisión:** tres manuscritos científico-técnicos de ingeniería en Markdown editable y PDF de lectura.

## Documentos de esta serie
1. **Manuscrito 06 - Identidad y consentimiento federado.** Audita y especifica el vínculo OIDC entre Prime y Django, los permisos granulares, la migración JIT segura y los motivos explícitos de fallback. Archivos: Manuscrito_06_CCB_Identidad_Consentimiento_Federado_2026.md/.pdf.
2. **Manuscrito 07 - Broker de conocimiento y memoria QAF.** Formaliza elegibilidad por finalidad, campos de perfil, conocimiento personal/episódico proyectable, ranking QAF y el bloqueo de herramientas personales en Commerce. Archivos: Manuscrito_07_CCB_Broker_Conocimiento_Memoria_QAF_2026.md/.pdf.
3. **Manuscrito 08 - Continuidad, seguridad y validación.** Define transición invitado->autenticado, epoch por sesión, protección contra mezcla de historiales, pruebas E2E y rollback. Archivos: Manuscrito_08_CCB_Continuidad_Cognitiva_Seguridad_Validacion_2026.md/.pdf.

## Dependencias y orden real de implementación

~~~text
M06: Vínculo Prime + Entra + Django y consentimiento explícito
   -> M07: Context Broker con nombre autorizado, preferencias y memoria seleccionada
      -> M08: transición de sesión, continuidad, pruebas adversariales y despliegue
~~~

**Precondición productiva:** comprobar el motivo de no reconocimiento del usuario mediante registro en ambos sistemas. Los flags VENDEDOR_CONTRATO_V2 y COMMERCE_LINKED_CONTEXT_ENABLED en true no prueban que exista vinculación ni permiso activo.

## Análisis comparativo con Business y Administrador
Se reutilizan patrones de **autorización de rol, fuente de verdad, proyecciones limitadas, memoria aislada y trazabilidad** de backend/api/superagent/business_evidence.py, business_conversation_context.py, admin_conversation_context.py, ai_role_isolation.py, canonical_privacy.py. No se transfieren permisos Business/Admin al vendedor.

## Estado y lectura correcta
- Los documentos son **especificaciones propuestas**, no commits que implementen el bridge ni prueba de funcionamiento en producción.
- Todas las ecuaciones de puntuación QAF son **hipótesis de ingeniería**, no resultados experimentales ni computación cuántica física.
- Las pruebas y umbrales son **criterios previstos**. Para validación deben ejecutarse CI, PostgreSQL/Redis staging, pruebas de dos cuentas y aceptación humana.
- Los datos de bienestar clínico, dispositivos y conversaciones completas **no** se exportan por defecto a Shop.
- El nombre de usuario no se toma del encabezado HTML como prueba de identidad Django; debe derivarse de un perfil Django verificado y permiso de finalidad.

## Gate de liberación
1. Diagnósticos de identidad y de consentimiento con resultado explicado (sin PII).
2. Pruebas de issuer + oid en Prime y Django y preservación de cuentas.
3. Proyección mínima con fuente, vigencia, confianza y autorización.
4. Revocación efectiva al siguiente turno; cero cruces de usuarios y roles.
5. UI sincronizada con transición login/logout; no heredar historial sensible.
6. CI, revisión de seguridad, canario y rollback verificados.

## Rutas de implementación
**Prime:** gotogym/vendedor/{identidad,consentimiento,personalizacion,paquete,conversacion,views}.py; gotogym/static/js/vendedor.js.
**Django:** backend/api/commerce_agent/{identity,context_broker,views,turn,continuity,evidence,narration}.py; backend/api/superagent/{ai_role_isolation,canonical_privacy}.py y servicios de memoria Personal.
**Pruebas:** gotogym/vendedor/test_identidad.py; test_consentimiento.py; backend/api/test_commerce_linked_context.py y pruebas adicionales propuestas en cada documento.

**Repositorio:** https://github.com/gotogymsaas/GoToGtymPrime
**Antecedentes históricos:** QAF/02_Manuscritos/Manuscrito_01_Identidad_Federada_Identity_Bridge_GoToGym.pdf, Manuscrito_02_Contexto_Comercial_Personalizacion_QAF.pdf, Manuscrito_03_Continuidad_Cognitiva_Omnicanal_Quantum_Coach_Prime.pdf.