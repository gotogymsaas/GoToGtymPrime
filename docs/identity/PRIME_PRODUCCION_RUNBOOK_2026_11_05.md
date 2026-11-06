# Universal Identity: puesta en producción de GoToGym Prime (noviembre de 2026)

## Fuentes de verdad comprobadas

- Código fuente: gotogymsaas/GoToGtymPrime; backend independiente de Django Quantum Coach.
- Deploy Prime: GitHub Actions \`.github/workflows/main_gotogymweb.yml\` -> App Service \`gotogym-prime\`, RG \`rg-gotogym-prime\`.
- Último deploy inspeccionado: run 41657931186, éxito del 3 nov 2026.
- Última auditoría Azure con evidencia detallada consultada: \`gotogymsaas/appdesplegada\`, run 41648184957 (3 nov 2026).
  Prime respondió HTTP 200 con \`{"enabled":false,"canary":false,"ready":false}\`; la identidad de auditoría recibió \`AuthorizationFailed\` al leer sus appsettings. No equivale a una lectura actual.
- **No se ha observado una sesión real OIDC Prime contra Microsoft Entra.** Ni CI verde ni Key Vault \`Resolved\` prueban autenticación.
- Las migraciones \`gotogym_oidc\` son aditivas; \`environments/azure/startup.sh\` ejecuta \`migrate --noinput\`.
- No confundir \`DJANGO_SECRET_KEY\` de Prime con el secreto de cliente \`OIDC_CLIENT_SECRET\`. Nunca copiar el secreto del Coach.

## Arquitectura objetivo (tres aplicaciones independientes)

Tenant external customer: \`GoToGym Universal Identity\` (ID \`fe3cd367-0570-48e7-8a35-a777b62cc6f9\`).
User flow: \`GoToGym-SignUpSignIn\`. El mismo user flow puede servir a varias aplicaciones cliente **registradas por separado**.

| Aplicación | Tipo de sesión | Callback OIDC | Cliente |
|---|---|---|---|
| Quantum Coach | Ticket efímero -> JWT propio de la App | \`https://api.gotogym.store/accounts/oidc/callback/\` | Cliente Coach (existente) |
| Shop/Prime | Sesión propia Django Prime | \`https://shop.gotogym.store/accounts/oidc/callback/\` | **Cliente Prime propio** |
| Developers | JWT/roles autorizados por su backend | Callback Developers registrado | Cliente Developers propio |

El identificador \`(issuer, oid)\` reconoce a la misma persona, pero **no** comparte \`user_id\`, planes, perfiles de bienestar, roles, contraseñas o cookies entre aplicaciones. La personalización del vendedor con datos del Coach requerirá más adelante un consentimiento explícito y una API privada con autorización.

## 1. Registro Entra External ID (intervención autorizada en el tenant externo)

1. Cambiar al directorio \`GoToGym Universal Identity\` en Entra admin center, **no** al directorio de la suscripción Azure de recursos.
2. Registros de aplicaciones -> revisar si **GoToGym Prime Shop** ya existe. Si no, crear registro Web (confidential client) dedicado a Prime. **No editar el cliente del Coach**.
3. En Autenticación: callback exacto \`https://shop.gotogym.store/accounts/oidc/callback/\`. Configurar URL de salida permitida \`https://shop.gotogym.store/\` según el panel.
4. External Identities -> User flows -> \`GoToGym-SignUpSignIn\` -> Applications: agregar la aplicación Prime; verificar que el mismo flujo usado en Coach la acepte.
5. Crear **únicamente si hace falta** una credencial de cliente para Prime. Guardar el campo **Valor** exclusivamente en Key Vault; no compartirlo por chat, terminal, logs o GitHub. Su caducidad requiere alertas y rotación preventiva.
6. Validar en un flujo controlado real las claims \`iss\`, \`aud\`, \`oid\`, \`email\` y \`email_verified\`. El correo realmente verificado es un requisito de identidad, no un booleano que debamos desactivar a ciegas.

## 2. Key Vault, identidad administrada y App Service Prime

- RG \`rg-gotogym-prime\`; App Service \`gotogym-prime\`.
- Usar una **credencial nueva y distinta** del \`gotogym-universal-identity-client-secret\` que usa el Coach. Nombre sugerido en Vault: \`gotogym-prime-oidc-client-secret\` (verificar que no exista uno apropiado antes de crearlo).
- Preferir el vault de producción autorizado con RBAC administrado. Habilitar identidad administrada de \`gotogym-prime\` y conceder permisos mínimos de lectura de *ese secreto* según el modo de autorización del vault.
- \`OIDC_CLIENT_SECRET\` será una referencia \`@Microsoft.KeyVault(SecretUri=https://<vault>.vault.azure.net/secrets/<secreto-prime>)\` sin versión fija para permitir rotación. No poner el valor plano en App Service ni GitHub.
- Confirmar estado de referencia \`Resolved\`. Esta comprobación **no** garantiza que el valor sea aceptado por Entra.
- Mantener \`DJANGO_SECRET_KEY\` de Prime **sin cambios**: alterarlo invalidaría sus sesiones y firmas existentes.

Appsettings **no secretas** requeridas en Prime:

\`\`\`text
OIDC_ISSUER=https://fe3cd367-0570-48e7-8a35-a777b62cc6f9.ciamlogin.com/fe3cd367-0570-48e7-8a35-a777b62cc6f9/v2.0
OIDC_DISCOVERY_URL=https://gotogymidentity.ciamlogin.com/fe3cd367-0570-48e7-8a35-a777b62cc6f9/v2.0/.well-known/openid-configuration
OIDC_CLIENT_ID=<ID DEL CLIENTE PRIME, NO EL DEL COACH>
OIDC_REDIRECT_URI=https://shop.gotogym.store/accounts/oidc/callback/
OIDC_POST_LOGOUT_REDIRECT_URI=https://shop.gotogym.store/
OIDC_SUBJECT_CLAIM=oid
OIDC_REQUIRE_EMAIL_VERIFIED_CLAIM=true
OIDC_ALLOW_AUTO_CREATE=false
OIDC_SOLO_GOTOGYM=false
UNIVERSAL_IDENTITY_CANARY_ENABLED=false
UNIVERSAL_IDENTITY_ENABLED=false
\`\`\`

\`ALLOWED_HOSTS\`, \`CSRF_TRUSTED_ORIGINS\`, \`SITIO_URL\` y \`DATABASE_URL\` permanecen con su configuración productiva correcta. No copiar variables del App Service Coach que pertenezcan a su propia base de datos o sesión.

## 3. Auditoría y seguridad, sin cambios

El repositorio contiene ahora un auditor de **solo lectura**:

\`\`\`bash
python3 -m unittest discover -s scripts/identity -p 'test*.py' -v
python3 scripts/identity/prime_readiness_audit.py
# Opcional cuando Azure CLI está autenticado con acceso de lectura al RG Prime:
python3 scripts/identity/prime_readiness_audit.py --azure
\`\`\`

Este auditor solo devuelve booleanos y categorías, nunca valores de appsettings ni secretos. Un resultado \`azure_rbac_denied\` significa que **esa identidad** no tiene lectura, NO que el recurso o secreto falte. El workflow \`Universal Identity Prime production readiness\` automatiza la lectura pública y realiza la lectura Azure si existen variables de identidad federada de GitHub con permisos RBAC.

Comprobaciones nativas del Django **real**, una vez configurada Prime (ejecutar con cuidado en el entorno autorizado):

\`\`\`bash
python gotogym/manage.py oidc_preflight --discovery --audit-preservation --strict
\`\`\`

Registrar la huella \`preservation.keyed_fingerprint\` antes del canario y después. El comando no modifica registros. No imprimir \`DJANGO_SECRET_KEY\`, correos, tickets ni passwords.

Los endpoints que **no** requieren secretos de usuario son:

- Público: \`https://shop.gotogym.store/accounts/identity/status/\` -> booleanos \`enabled,canary,ready\`.
- Diagnóstico: \`https://shop.gotogym.store/accounts/identity/preflight/\` -> **solo personal de Prime** autenticado.

## 4. Canary Prime (no usar flag global todavía)

Solo cuando \`ready=true\` y el preflight es satisfactorio:

\`\`\`text
UNIVERSAL_IDENTITY_CANARY_ENABLED=true
OIDC_CANARY_OBJECT_IDS=<oid exacto del usuario de prueba autorizado>
UNIVERSAL_IDENTITY_ENABLED=false
OIDC_ALLOW_AUTO_CREATE=false
\`\`\`

Entrar desde \`https://shop.gotogym.store/accounts/acceso/?sso=1\` con el usuario ya autenticado en Quantum Coach. Si ese correo ya existe en Prime, la primera visita solicita su **contraseña local de la tienda** para vincularla una única vez. Si no existe todavía y el alta automática está cerrada, no se creará: decidir activación con aceptación de términos y prueba de provisión. No copiar usuarios desde la BD del Coach.

Pruebas exigidas: account linking con contraseña correcta/incorrecta, rechazos de tokens, sesión privada/normal, usuario inactivo, staff/afiliado, carrito y \`next\` hasta checkout, direcciones, términos obligatorios, segundo ingreso sin nueva vinculación, logout de Prime y acceso heredado.

## 5. Apertura global Prime y rollback

Solo con las pruebas E2E reales aprobadas y la huella conservada:

\`\`\`text
UNIVERSAL_IDENTITY_ENABLED=true
UNIVERSAL_IDENTITY_CANARY_ENABLED=false
OIDC_SOLO_GOTOGYM=false
\`\`\`

El formulario de contraseña Prime sigue disponible (\`/accounts/acceso/?legacy=1\`). **No** cambiar \`OIDC_ALLOW_AUTO_CREATE\` hasta acordar y probar la incorporación de cuentas Prime nuevas con términos/privacidad y sin duplicación. Tampoco encender \`OIDC_SOLO_GOTOGYM\` hasta verificar la recuperación.

Rollback: \`UNIVERSAL_IDENTITY_ENABLED=false\`, \`UNIVERSAL_IDENTITY_CANARY_ENABLED=false\`; conservar tablas de vínculos, cuentas, historiales, pedidos y credenciales existentes. Un logout de Prime **no revoca automáticamente** JWT emitidos previamente para Quantum Coach ni Developers.

## Lo que NO puede certificar un repositorio ni un workflow de build

- Que el registro Prime en **otro tenant** esté creado/asociado al flujo.
- Que la credencial de Prime exista y sea correcta en el Key Vault real.
- Que una app autorizada haya iniciado sesión satisfactoriamente en un navegador real.
- Que todas las cuentas de Prime y Coach estén vinculadas (no deben fusionarse por correo).
- Que el vendedor Shop ya vea medidas, datos de salud o memoria personal del Coach.

No afirmar \`100 % implementado\` ni activar el flag global cuando alguna de estas evidencias falte.
