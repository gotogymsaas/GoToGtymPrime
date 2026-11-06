# GoToGym Shop / Prime — flujo comercial correcto para Universal Identity

Fecha: 5 de noviembre de 2026. Alcance: `shop.gotogym.store` y su Django propio.

## Diagnóstico de la pantalla real

En la captura de `/accounts/acceso/?sso=1` solo aparecen usuario/contraseña y registro local.
El código confirma que `?sso=1` **solo muestra el botón del proveedor si el App Service
ha habilitado OIDC previamente**. No activa el servicio ni sus credenciales.

La última auditoría pública de Prime devolvió `enabled=false, canary=false, ready=false`.
Por tanto, la pantalla no prueba un fallo del formulario: el proveedor aún no puede usarse
en la tienda. El mensaje de prueba debería explicar esta limitación y ofrecer el acceso local.

## Objetivo de negocio

**Una identidad externa GoToGym; una cuenta comercial Prime por cliente, sin fusionar
bases de datos.** El cliente compra en Shop con el mismo inicio de sesión que utiliza
en Quantum Coach, pero el sistema mantiene el historial de compras, direcciones,
afiliaciones y permisos en Prime. No se transfieren contraseñas ni información de
salud automáticamente.

### Flujo A: usuario que explora

1. Puede descubrir ropa, precios y contenido de la tienda sin autenticarse.
2. Agrega productos al carrito local/de sesión (se conserva).
3. Cuando solicita ver su perfil, historial o finalizar compra, el sitio abre
   `/accounts/acceso/?next=<destino-local-seguro>`.
4. Si SSO está **preparado y habilitado**, presentar **«Continuar con GoToGym»**
   como opción principal, y **«Contraseña habitual de Shop»** como respaldo.
5. Al concluir el inicio de sesión, retornar al destino seguro y conservar carrito
   y cantidades. No convertir páginas de login o registro en `next`.

### Flujo B: usuario de Coach con cuenta Prime vinculada

1. Prime inicia Authorization Code + PKCE contra su **propio cliente** registrado
   en el tenant `GoToGym Universal Identity`.
2. Entra puede aprovechar su sesión previa de Quantum Coach: no comparte cookies
   de Django ni tokens de Prime con Coach.
3. Prime valida `iss`, `aud`, firma, `nonce`, `state`, `oid`, y la garantía
   de correo verificado.
4. Busca vínculo único `(issuer, oid)`; inicia sesión en el **mismo user_id Prime**,
   nunca crea una cuenta duplicada. Roles y direcciones permanecen intactos.
5. Retorna al carrito/producto/checkout.

### Flujo C: misma identidad, cuenta Prime existente pero no vinculada

1. El correo puede ayudar a localizar la cuenta existente, **nunca equivale a prueba
   de propiedad por sí mismo**.
2. Solicitar una sola vez la **contraseña local de Prime** (no la del Coach) para
   confirmar el vínculo. Aplicar límites de intentos y CSRF.
3. Preservar `user_id`, hash de contraseña, pedidos, datos de envío y roles.
4. Guardar vínculo inmutable `(issuer, oid)`, sin reescribir la cuenta.
5. En posteriores sesiones omitir la contraseña local de vinculación.

### Flujo D: usuario de Coach que aún no es comprador de Prime

Situación **actual**: `OIDC_ALLOW_AUTO_CREATE=false`. Una identidad Entra válida
sin cuenta Prime no genera usuario comercial. No presentar esta experiencia como
«cuenta Shop creada automáticamente».

Objetivo propuesto **para una etapa posterior**, sujeto a requisitos legales y
pruebas reales: completar el registro de cliente con consentimiento de términos/
privacidad explícito, crear un usuario Prime de permisos mínimos ligado al `oid`
y regresar al checkout. Si ya existe el correo, llevar al flujo C y **no** crear
otra cuenta. El código tiene un mecanismo de aceptación de términos tras el
primer inicio de sesión OIDC; debe validarse su compatibilidad con el alta
automática antes de encenderla.

### Flujo E: error de Entra, 2FA o recuperación

- Mantener disponible el acceso habitual de Prime y recuperación de contraseña.
- Una prueba canaria no lista no debe terminar en pantalla engañosa o loop.
- Dejar `OIDC_SOLO_GOTOGYM=false` hasta certificar el acceso de respaldo.
- No mostrar mensajes internos ni valores de secretos al comprador.

## Identidad no equivale a compartir sabiduría del Coach

La identidad común identifica a la persona, pero el vendedor IA **no debe**
recuperar automáticamente historial, hábitos, datos de salud o medidas sensibles
del Coach. Requiere consentimiento granular por finalidad, permisos adecuados,
servicio backend-a-backend, auditoría de consultas y revocación. Primer paso:
personalización con productos, preferencias y pedidos **de la propia tienda**.

## Puerta de salida a producción

- `/accounts/identity/status/`: `ready=true`.
- La aplicación Entra Prime es diferente de Coach, con callback Shop.
- Secreto propio de Prime resuelto por Key Vault; ningún valor en GitHub.
- Canary autorizado comprueba A/B/C, carrito, checkout, permisos, términos y
  acceso clásico, además de identidad incorrecta y fallos del proveedor.
- El flujo D requiere decisión de negocio y pruebas explícitas antes de habilitar
  el alta por Entra.
- Solo entonces activar `UNIVERSAL_IDENTITY_ENABLED=true` y mantener
  `OIDC_SOLO_GOTOGYM=false`. Disponer de rollback a `false`.

Nota: estas fases describen objetivo de producto y estado observable; una
prueba de CI o el mero enlace `?sso=1` no acreditan login real.
