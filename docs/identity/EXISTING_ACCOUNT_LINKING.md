# Universal Identity: conservar la cuenta existente

## Contrato de experiencia

Una persona que ya tiene cuenta en GoToGym Quantum Coach **no debe registrarse nuevamente en la aplicación**. Después de activar Entra y completar el registro/inicio de sesión en el proveedor (la identidad de Entra es independiente), el OIDC encuentra la cuenta local correspondiente y **solicita la contraseña de GoToGym una única vez** para vincularla. No se vincula solo por correo y no se importa la contraseña a Entra.

Cuando la prueba local es válida, se almacena un vínculo entre `(issuer, oid)` y el identificador interno **existente**. Los siguientes logins con la misma identidad validada reutilizan esa cuenta. El usuario mantiene su contraseña y acceso anterior mientras esté disponible, así como su plan, suscripción, historial y permisos locales; las pruebas de compatibilidad usan datos sintéticos y deben complementarse con auditoría de preservación y canarios en producción.

El formulario explica la diferencia entre la contraseña local y la del proveedor. El enlace está limitado por intentos en base de datos, protegido con CSRF y consume un flujo OIDC temporal con state, nonce y PKCE. No registrar contraseñas ni tokens.

## Límites reales

- **Coach y Prime mantienen sus propias tablas de usuarios.** Que las cuentas tengan el mismo correo no significa que sus IDs, compras, historiales o permisos se fusionen. El mismo Entra tenant permite una identidad común; cada producto conserva y administra sus datos. Vincular en Prime puede requerir su propia comprobación de contraseña de tienda.
- **Developers** aprovisiona permisos exclusivamente mediante un binding administrativo validado por `issuer + oid`; no debe heredar planes, roles o permisos solo por correo.
- Si el correo del proveedor cambió y no coincide con el de la cuenta local, no crear o fusionar silenciosamente una cuenta: utilizar un proceso de soporte con verificación de titularidad o una futura vinculación iniciada desde sesión local autenticada.
- Una persona que utiliza segundo factor local no debe perderlo mediante SSO. El flujo actual de Coach deniega SSO para esos usuarios y conserva la ruta local hasta implementar una política MFA equivalente debidamente probada.
- Un nuevo registro en **Entra** (si aún no existe) no equivale a crear una segunda cuenta de **GoToGym**.
- Con flags desactivados, seguir entrando con el método existente. No afirmar que el nuevo login esté operativo hasta las pruebas E2E con Microsoft Entra y despliegue verificado.

## Aceptación antes de habilitar

1. Una cuenta existente puede seguir entrando con su contraseña original.
2. Primer SSO con email coincidente solicita prueba de la contraseña local, no crea otro usuario y no vincula si falla.
3. La prueba válida conserva el mismo user_id, password hash, plan, roles, suscripción, historial y carrito (según el producto).
4. El segundo SSO con el mismo `issuer + oid` reutiliza el vínculo sin pedir otra vez la contraseña local.
5. Una cuenta con correo distinto, duplicado o privilegios especiales no se fusiona por inferencia.
6. Rollback de los flags restaura la ruta previa sin eliminar vínculos o tablas; comprobar que los tokens SSO previamente emitidos conservan la protección de revocación.

No copiar usuarios, hashes de contraseñas, secretos ni tokens entre bases de datos para simular un SSO.
