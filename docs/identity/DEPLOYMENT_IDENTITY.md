# Configuración exacta y verificación

No contiene credenciales ni afirma que Azure esté configurado. Todas las URL deben ser HTTPS. Usar tres client_id distintos en el mismo tenant.

| Aplicación | Callback del proveedor | Retorno del puente al frontend |
|---|---|---|
| Prime | https://shop.gotogym.store/accounts/oidc/callback/ | No necesita puente: sesión Django propia |
| Developers | https://HOST_BACKEND_DEVELOPERS/api/v1/auth/identity/callback | https://developers.gotogym.store/login |
| Coach | https://api.gotogym.store/accounts/oidc/callback/ | https://app.gotogym.store/pages/auth/indexInicioDeSesion.html |

HOST_BACKEND_DEVELOPERS es un valor pendiente: sustituir por el origen real del backend. No registrar ese texto en Entra.

## Variables compartidas

OIDC_ISSUER (exacto del discovery), OIDC_DISCOVERY_URL si corresponde, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_REDIRECT_URI. Guardar secretos en la configuración segura del servicio. No crear archivos .env con valores reales en Git.

## Prime

OIDC_SUBJECT_CLAIM=oid; OIDC_SOLO_GOTOGYM=false inicialmente. OIDC_POST_LOGOUT_REDIRECT_URI debe estar registrado. El módulo está incluido en gotogym/gotogym_oidc para evitar depender de credenciales de un repositorio privado durante build.

```bash
python manage.py migrate gotogym_oidc
python manage.py test accounts.test_oidc
```

## Developers

Node >=22. Configurar OIDC_ENABLED=true sólo al terminar pruebas; OIDC_FRONTEND_CALLBACK, OIDC_BINDINGS_JSON y JWT_SECRET robusto. El frontend debe apuntar al backend Developers en VITE_API_URL; un backend Django no tiene los mismos endpoints /api/v1/auth/identity.

OIDC_BINDINGS_JSON es un arreglo de objetos con issuer, oid, active y user. user contiene id, email, role, scopes, tenant {tenantId, organizationId, membershipId} y tokenType=user. Los valores los asigna el administrador desde una fuente de membresías validada. No cargar la lista de usuarios demo ni resolver por correo. Ejemplo de formato (no credenciales):

```json
[{"issuer":"https://TENANT.ciamlogin.com/TENANT_ID/v2.0","oid":"OID_REAL","active":true,"user":{"id":"ID_LOCAL_REAL","email":"usuario@example.com","role":"end_user","scopes":["profile:read:self"],"permissions":["profile:read:self"],"tenant":{"tenantId":"TENANT_LOCAL","organizationId":"ORG_LOCAL","membershipId":"MEMBRESIA_LOCAL"},"tokenType":"user"}}]
```

El nuevo SSO usa OIDC_DATABASE_URL y PostgreSQL. Aplicar backend/migrations/001_universal_identity.sql con una identidad de migración; dar al runtime sólo SELECT/INSERT/DELETE sobre esas dos tablas. En producción el cliente exige TLS y valida el certificado. Flujos y tickets se consumen con DELETE RETURNING atómico, compartido entre procesos. Fuera de NODE_ENV=test no hay fallback en memoria o JSON. Probar concurrencia en staging antes de escalar. El proveedor OAuth para terceros sigue usando su persistencia heredada y no queda modernizado por este cambio.

```bash
psql "$OIDC_DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/001_universal_identity.sql
```

```bash
npm ci --ignore-scripts
npm run build
npm test -- --runInBand
```

## Coach

UNIVERSAL_IDENTITY_ENABLED=false por defecto. OIDC_FRONTEND_CALLBACK es único, sin query ni fragmento. OIDC_ALLOW_AUTO_CREATE=false por defecto: primero aprovisionar/enlazar usuarios existentes. Si se habilita alta nueva, revisar aceptación de términos y onboarding con el equipo de producto. No se asignan organizaciones o planes desde claims.

```bash
python manage.py migrate gotogym_oidc
python manage.py migrate universal_identity
python -m django test universal_identity --settings=universal_identity.test_settings
```

Las pruebas anteriores usan auth.User y un payload simulado para aislar el puente. No son la suite completa del Coach. Probar también la integración con api.User, UserSerializer y _build_post_login_context del despliegue real.

## Prueba de aceptación real

En navegador: entrar a Prime, abrir Developers, abrir Coach; confirmar que no se piden credenciales repetidas mientras el IdP tenga sesión y que oid sea el mismo. Verificar que scopes y tenants no se trasladan entre aplicaciones. Probar cuenta inactiva, correo duplicado, vinculación con contraseña errada, consentimiento, usuario con 2FA local, tickets vencidos y repetidos. Cerrar Prime debe cerrar su sesión y pedir el cierre del IdP; no debe afirmarse que invalida JWT ya emitidos en las otras aplicaciones. Ningún paso de este documento fue ejecutado en Azure por esta entrega.
