# Universal Identity - plan y trazabilidad

Fecha: 2026-11-02. Alcance confirmado por el propietario: GoToGtymPrime, gotogymdevelopers y appdesplegada.
Identidad central propuesta: Microsoft Entra External ID; cada aplicación conserva su autorización y sus credenciales locales.

## Inventario y pendientes

| ID | Trabajo | Entrega de código | Condición antes de activar |
|---|---|---|---|
| I01 | Cliente Django compartido con PKCE, validación RS256/iss/aud/nonce/azp y consumo DB del flujo | login/packages/django | Migraciones y tenant real |
| I02 | Evitar enlace por correo ambiguo y exigir contraseña local | gotogym_oidc/adapter.py y views.py | Verificar cuentas duplicadas existentes |
| I03 | Integrar Prime, carrito, términos y cierre POST | GoToGtymPrime/gotogym/accounts | Configurar cliente Entra independiente |
| I04 | Impedir saltar aceptación de términos navegando a otra vista | RequireOIDCTermsMiddleware | Revisar texto vigente de términos |
| I05 | Cliente OIDC Node independiente del proveedor OAuth para terceros | gotogymdevelopers/backend | Cliente Entra, bindings explícitos y runtime Node 22 |
| I06 | Permisos y tenant por binding local (issuer, oid), sin roles tomados del token | identity.service.ts | Aprovisionar usuarios y membresías autorizados |
| I07 | Inhabilitar acceso a usuarios demo en producción por defecto | auth.service.ts | No habilitar ALLOW_DEMO_LOGIN en producción |
| I08 | Botón SSO y entrega por ticket PKCE en Developers | frontend/auth/identity.ts | Configurar VITE_API_URL al backend Developers |
| I09 | Puente OIDC a JWT del Coach con ticket de 60 s de un uso | appdesplegada/backend/universal_identity | Migraciones, cliente Entra y Origin exacto |
| I10 | Reutilizar contexto post-login y serialización del Coach | universal_identity/views.py | Prueba completa con modelos y datos de staging |
| I11 | No omitir 2FA local: denegar SSO a cuentas con 2FA activado | CoachAdapter y exchange | MFA federado/step-up es trabajo posterior, login local disponible |
| I12 | Botón SSO y callback sin JWT en URL del Coach | indexInicioDeSesion.html | Validación de navegador y PWA en staging |
| I13 | Suites y CI de protocolo/puente/Node | workflows y pruebas | Ejecutar CI en GitHub y revisar resultados |
| I14 | Registro real en Entra, flujos de usuario y correo verificado | No ejecutado: requiere tenant | Credenciales/tenant configurados en Azure, sin secretos en Git |
| I15 | SSO real entre tres aplicaciones | Pendiente externo | Misma oid con distintos client_id, casos de navegador normal/privado |
| I16 | Persistencia distribuida de flujos/tickets de identidad Developers | Repositorio PostgreSQL y migración SQL implementados | Crear DB, aplicar SQL y ejecutar pruebas reales de concurrencia; el proveedor OAuth para terceros conserva su store heredado |
| I17 | Revocación global inmediata y cierre de todas las sesiones locales | No implementada | SSO no equivale a single logout distribuido; diseñar back-channel/revocación y política de JWT |
| I18 | Unificar MFA federado y revisar consentimientos de usuarios nuevos | Pendiente de política | Nunca inferir MFA verificado por correo o por existencia de token |

## Orden de activación

1. Integrar los cambios de código después de revisar las PR y CI. Mantener flags apagados.
2. Ejecutar migraciones del módulo compartido en Prime y Coach, y universal_identity en Coach.
3. Crear/configurar tenant externo y un cliente por aplicación. Verificar issuer exacto del discovery y oid en ID tokens reales.
4. Exigir verificación de correo en el user flow. Si Entra emite email_verified, activar REQUIRE_EMAIL_VERIFIED_CLAIM.
5. Aprovisionar bindings de Developers por oid, no por email. Configurar acceso y tenant con privilegios mínimos.
6. Validar registro, vinculación, cambio de correo, cuenta inactiva, 2FA local, carrito, términos, callback repetido, pestaña distinta, fallo del IdP y rollback.
7. Ejecutar prueba cruzada de SSO en staging; después habilitar canario y observar fallos/latencia sin registrar tokens.

## Criterios que bloquean el lanzamiento

Sin una segunda aplicación real no se puede afirmar SSO. Sin tenant no se puede afirmar compatibilidad verificada con Entra. El nuevo SSO de Developers exige PostgreSQL fuera de pruebas; no admite fallback JSON. Su proveedor OAuth para terceros conserva un store heredado y debe evaluarse por separado antes de escalar toda la aplicación. Sin validación de MFA no se habilita acceso SSO de cuentas con 2FA local. Los ID tokens del proveedor nunca autorizan directamente APIs de otra aplicación.

## Reversión

Prime: retirar OIDC_ISSUER o desactivar OIDC_SOLO_GOTOGYM; acceso local disponible.
Developers: OIDC_ENABLED=false. No habilitar usuarios demo como mecanismo de emergencia en producción.
Coach: UNIVERSAL_IDENTITY_ENABLED=false. El acceso por contraseña sigue su ruta actual.
No borrar enlaces de identidad ni revertir migraciones con datos para apagar la función.
