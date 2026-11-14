# Cognitive Commerce Bridge — despliegue y pruebas reales (2026-11-14)

## Estado
Implementación coordinada en dos PR: Prime #64 y appdesplegada #884. No confundir
código fusionado o CI verde con imagen publicada y contrato funcional de usuario.

## Precondiciones
- Respaldo actual de las bases Prime y Django.
- Mismo OIDC issuer verificado en ambas aplicaciones, sujeto `oid`, vínculo
  existente para la cuenta de prueba en **ambas** tablas ExternalIdentityLink.
- Credenciales distintas de servicio y de identidad, ambas referencias Key Vault
  resueltas en cada aplicación; no imprimir ni copiar secretos.
- `VENDEDOR_CONTRATO_V2=true` en Prime y `COMMERCE_LINKED_CONTEXT_ENABLED=true`
  en appdesplegada (solo después de verificar la clave y el vínculo).
- Cuenta de prueba con consentimiento **explícito** y vigente para
  `profile.display_name` y `profile.basic`. No se concede por registro.
- Confirmar despliegue de appdesplegada antes de habilitar el nuevo scope en Prime.

## Secuencia segura
1. Integrar y publicar Django, confirmar versión e identidad de imagen real. Ejecutar
   sus pruebas API: test_commerce_linked_context, test_commerce_cognitive_bridge.
2. Verificar disponibilidad de Django `/healthz` y que el contrato v2 acepta
   `profile.display_name` en la prueba sintética firmada.
3. Respaldar Prime; ejecutar migración aditiva `vendedor.0004_display_name_consent`
   en el entorno de despliegue autorizado antes de habilitar el código nuevo.
4. Integrar y desplegar Prime; comprobar que `/es/vendedor/estado/` responde
   JSON con `mode`, `epoch` opaco y `personalization_ready`, sin PII.
5. Iniciar sesión mediante el proveedor OIDC existente. Si `mode=link_required`,
   completar enlace seguro de cuenta; **no** vincular por correo o nombre.
6. En Mi cuenta → Personalización, activar voluntariamente `Saludarme por mi nombre`
   y `Perfil deportivo básico` (no activar scopes no deseados).
7. Verificar que `/es/vendedor/estado/` pase a `mode=linked`.
8. Preguntar `¿Cómo me llamo?` y `¿Cuál es mi deporte favorito?`: el Coach
   debe utilizar evidencia real o explicar que el dato falta, sin inventarlo.
9. Revocar `profile.display_name`: volver a preguntar; el nombre no debe
   aparecer en nuevo contexto ni historial autorizado.
10. Probar visitante → login → cambio de cuenta → logout en la misma pestaña:
    rotar conversación/epoch y descartar historial anterior.
11. Ejecutar prueba con dos identidades distintas para confirmar cero cruces.

## Diagnóstico seguro
### Prime (sesión del mismo usuario)
GET https://shop.gotogym.store/es/vendedor/estado/
- anonymous: visitante
- link_required: login local o falta relación OIDC con issuer esperado
- consent_required: vínculo en Prime, pero ningún permiso vigente
- identity_not_ready: contrato o credenciales incompletos
- linked: Prime puede emitir aserción; todavía se debe confirmar vínculo Django.

### Django (solo operador con CLI del backend)
`python manage.py commerce_ccb_diagnose --user-id <ID_DJANGO>`
No imprime nombre, correo, oid ni secreto. El ID debe verificarse de forma
autorizada, sin copiarlo al chat. Confirmar `oidc_link_for_user=true`,
`verified_display_name_available=true` y flags. El consentimiento se valida
por separado desde Prime; el comando no puede certificarlo.

### Telemetría Django (privada)
- `commerce_identity_rejected reason=not_linked`: sin vínculo Django.
- `commerce_identity_rejected reason=issuer`: issuer distinto.
- `commerce_context_missing reason=identity_absent`: Prime no emitió identidad.
- `commerce_context_result linked=true fact_count=N`: el broker proyectó hechos,
  pero N=0 puede ser correcto si no hay campos autorizados.
- No registrar conversaciones, emails, tokens, perfiles ni secretos.

## Gate de aceptación y rollback
No publicar a todos hasta que CI esté verde, migración aplicada, health check
correcto, usuario de prueba vinculado, consentimiento explícito, exactitud del
nombre y deporte verificadas, revocación inmediata y cero mezcla entre dos
usuarios. Ante anomalía: desactivar `VENDEDOR_CONTRATO_V2` en Prime y
`COMMERCE_LINKED_CONTEXT_ENABLED` en Django. Mantener tablas y migración;
nunca borrar usuarios, planes, historial o vínculos como rollback.

## Limitación deliberada
El nuevo broker expone nombre de presentación verificado y hechos deportivos
estructurados previamente autorizados; no concede a Commerce acceso directo a
RAG episódico crudo, historiales de salud, wearables, Business o Admin. El
manuscrito 07 contempla ampliar esta exportación con autorización adicional,
clasificación y pruebas de privacidad.
