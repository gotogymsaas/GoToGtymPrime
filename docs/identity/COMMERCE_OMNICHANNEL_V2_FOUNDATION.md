# Commerce Omnichannel v2 — consentimiento en Prime (fase 1)

Basado en los seis manuscritos QAF de noviembre de 2026. Estado: **fundacion de consentimiento**, no hay un Context Broker ni acceso a perfiles del Coach.

## Endpoint implementado

`GET /es/vendedor/consentimiento/` devuelve `linked`, `version` y un mapa de cuatro scopes. Ninguno se concede por defecto.
`POST /es/vendedor/consentimiento/` recibe JSON `{"scope":"profile.basic","allowed":true}`, con sesion y CSRF. Se rechaza si el usuario no tiene `ExternalIdentityLink`.
Scopes: `profile.basic`, `sports.preferences`, `experiences.summary`, `tailoring.measurements`.

La revocacion actualiza el permiso en la base Prime y genera un evento de auditoria. No hay lector desde Coach: la futura pasarela debera comprobar y hacer cumplir las revocaciones en su propia frontera antes de consultar datos.

## Pendientes de seguridad obligatorios antes de activar contexto v2

1. Asercion autentificada de servidor a servidor, ligada a (issuer, oid), audiencia commerce, iat/exp <= 60s y jti de un solo uso.
2. Resolver el enlace en `appdesplegada` por (issuer, oid), **no por correo, nombre ni shop_u_**.
3. Mantener una decision de permiso vigente de la fuente autorizada; no confiar en flags enviados por navegador ni en campos de un paquete v1.
4. Context Broker que proyecte campos aprobados y con procedencia, sin historia clinica, datos crudos de wearables ni transcripciones.
5. Versionar contrato v2 sin tocar `vendedor/contrato.py` v1; fallback anonimo si no hay vinculo, consentimiento o Coach.
6. Interfaz de opt-in, revocacion inmediata y pruebas E2E con dos usuarios; sin presentar personalizacion hasta completar la cadena.
7. Probar migracion aditiva, CSRF, aislamiento entre usuarios, expiracion, rotacion de claves y rollback.

No habilitar personalizacion automaticamente ni copiar el secreto OIDC del Coach. La ruta de consentimiento nunca transmite medidas ni PII a otro servicio.
