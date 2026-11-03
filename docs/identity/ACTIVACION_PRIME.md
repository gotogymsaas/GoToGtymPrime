# Activación y reversión del inicio de sesión unificado en Prime

Estado: código y pruebas listos; nada de esto se ha ejecutado en Azure ni contra Entra. Los pasos marcados como externos requieren acceso al tenant o a la configuración de Prime.

## Antes de empezar (externo)

1. Registrar en el tenant GoToGym Universal Identity una aplicación propia de Prime, plataforma Web, con la callback `https://shop.gotogym.store/accounts/oidc/callback/` y la URI de cierre `https://shop.gotogym.store/`. No reutilizar el cliente ni el secreto del Coach.
2. Asociarla al flujo `GoToGym-SignUpSignIn` y exigir correo verificado en el flujo.
3. Guardar el secreto en Key Vault y referenciarlo desde la configuración de la app de Prime con una identidad administrada que pueda leerlo.
4. Confirmar en un token real que llegan `iss`, `aud`, `oid` y `email`, y si llega `email_verified`. Sin ese claim hay que decidir entre `OIDC_REQUIRE_EMAIL_VERIFIED_CLAIM=false` (solo con verificación de correo garantizada por el flujo) o configurar el claim.

## Orden de activación

Todo con las banderas apagadas hasta el paso 4.

1. Desplegar el código con las variables `OIDC_*` cargadas y `UNIVERSAL_IDENTITY_ENABLED=false`, `UNIVERSAL_IDENTITY_CANARY_ENABLED=false`. `POST /accounts/oidc/start/` debe seguir respondiendo 404 y el login con contraseña debe seguir funcionando.
2. Ejecutar `python manage.py migrate gotogym_oidc` (migraciones 0001 a 0003; solo agregan tablas).
3. Ejecutar `python manage.py oidc_preflight --discovery --audit-preservation --strict`. Guardar la salida (no contiene secretos ni datos de personas): la huella `keyed_fingerprint` es el punto de comparación.
4. Canary: `UNIVERSAL_IDENTITY_CANARY_ENABLED=true` y `OIDC_CANARY_OBJECT_IDS=<oid de la cuenta de prueba>`. Probar con `/accounts/acceso/?sso=1`.
5. Pruebas con cuentas de prueba, nunca con contraseñas reales:
   - alta nueva (solo si `OIDC_ALLOW_AUTO_CREATE=true`, con términos obligatorios);
   - cuenta existente que vincula su identidad pidiendo su contraseña local;
   - cuenta que sigue entrando con su contraseña;
   - cuenta de personal (`is_staff`) y de afiliado conservan sus permisos;
   - un `oid` fuera de la lista no entra ni crea nada;
   - cerrar sesión cierra también la del proveedor y permite autenticarse de nuevo;
   - carrito de invitado conservado.
6. Repetir `oidc_preflight --audit-preservation`. Solo las cuentas de prueba pueden cambiar la huella; para el resto debe ser idéntica.
7. Abrir a todos: `UNIVERSAL_IDENTITY_ENABLED=true`. Mantener `OIDC_SOLO_GOTOGYM=false` hasta validar las cuentas existentes.

## Qué no cambia

No se migran contraseñas, no se reemplazan identificadores internos, no se vincula por correo sin la contraseña local, y los roles y permisos (`is_staff`, `is_superuser`, `es_afiliado`, segmentos) siguen siendo locales: ningún claim del proveedor los asigna.

## Reversión

1. `UNIVERSAL_IDENTITY_ENABLED=false` y `UNIVERSAL_IDENTITY_CANARY_ENABLED=false` (o retirar `OIDC_ISSUER`).
2. Comprobar que `/accounts/oidc/start/` responde 404 y que el login con contraseña entra.
3. Repetir `oidc_preflight --audit-preservation`.

No borrar vínculos ni revertir migraciones: las tablas son aditivas y apagarlas no las toca. Las sesiones ya abiertas siguen hasta que caduquen o cierren sesión.

## Límites

- El cierre de sesión en Prime cierra la sesión de Prime y pide la del proveedor; no invalida lo emitido por el Coach ni por Developers.
- Prime no tiene planes ni suscripciones: lo que se preserva son las cuentas, contraseñas, permisos, afiliación, pedidos y direcciones.
- El flujo completo contra Entra está sin probar. Las pruebas usan un proveedor simulado.


## Estado de preparación sin activar el login

La tienda expone una ruta de solo lectura **no localizada**:

```text
GET https://shop.gotogym.store/accounts/identity/status/
```

Respuesta mínima: `{"enabled":false,"canary":false,"ready":false}` (los booleanos dependen de la configuración real). La comprobación exige cliente OIDC y secreto resuelto, callback, `oid`, migraciones aplicadas y discovery válido con issuer exacto. Para el canario exige identificadores autorizados. Es un sondeo público limitado a booleanos; no devuelve emails, IDs, tokens, contraseñas ni motivos internos de error. Su caché interna dura 15 segundos y falla cerrado si el proveedor o la base de datos no responden.

`ready=true` significa preparación técnica, **no** que ya se probó el login real con Entra. `enabled=true` solo corresponde a modo global configurado **y** listo; `canary=true` indica canario acotado sin abrir el acceso global. Mantener el login heredado mientras se ejecutan pruebas E2E con usuarios autorizados y se comprueba la preservación del carrito y las cuentas. Este endpoint no crea usuarios ni ejecuta migraciones.


## Diagnóstico administrativo de bloqueos (sin Azure RBAC)

Una persona con sesión vigente de **personal autorizado de Prime** (`is_active=True` e `is_staff=True`) puede consultar:

```text
GET https://shop.gotogym.store/accounts/identity/preflight/
```

Un cliente o visitante no puede acceder a los resultados; es redirigido al login administrativo.
La ruta funciona incluso con los flags OIDC global y canario apagados y no altera
cuentas, planes, sesiones, migraciones, credenciales ni la configuración de Azure.

La respuesta incluye `mode`, `ready` y una lista de comprobaciones conocidas
`{check,ok,blocking}`, sin campos `detail`, variables de entorno, tokens,
identificadores personales ni errores internos. Para diagnosticar `ready:false`:
si falla `issuer_configurado`/`client_id_configurado` o `client_secret_presente`,
comprobar que el registro **Prime** de Entra existe y que Azure tiene sus ajustes;
si falla `client_secret_resuelto`, revisar identidad administrada, permisos de
Key Vault y estado de referencia `Resolved` sin leer el secreto; si falla
`migraciones_aplicadas`, revisar el plan de migraciones con el administrador
de despliegues antes de tocar PostgreSQL; si falla `discovery_accesible` o
`issuer_coincide_con_el_discovery`, comprobar endpoints y respuesta real
del proveedor. `ready:true` **no prueba** una autenticación E2E real.

Esta ruta facilita el diagnóstico cuando el workflow de GitHub solo recibe
`AuthorizationFailed` en el RG de Prime. No elimina la necesidad de corregir
los permisos mínimos, validar los registros de aplicaciones en el tenant External
ID y realizar un canario real con usuarios de prueba.
