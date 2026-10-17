# Configuración del correo de GoToGym

Procedimiento completo con el que se dejó funcionando el correo de la tienda (17 de octubre de 2026): qué se decidió, qué se configuró en Azure, qué variables lleva la aplicación, cómo se probó y cómo mantenerlo. No contiene claves ni secretos. El estado actual y los datos operativos están en [DESPLIEGUE.md](DESPLIEGUE.md), sección Correo.

## 1. Qué hace la aplicación con el correo

La tienda envía correos en cuatro situaciones:

| Situación | Correos |
|---|---|
| Recuperar contraseña | Enlace para elegir una contraseña nueva |
| Pedido | Recibido (pendiente de pago), confirmado, enviado y cancelado |
| Programa de afiliados | Solicitud recibida, aprobada (bienvenida), rechazada, baja solicitada y efectiva, terminación, validación extendida, cambio de comisión, avisos generales y comisión pagada |
| Pruebas | `probar_correo` y `previsualizar_correos` |

Todos salen como HTML de marca con una versión de texto. Si el envío falla, la acción que lo originó no se deshace: la compra, el pago o el cambio de estado quedan registrados y el error va al log.

La aplicación habla SMTP estándar. Por eso el proveedor se puede cambiar sin tocar el código: solo cambian las variables de entorno.

## 2. Decisión del proveedor

Se evaluaron proveedores SMTP gratuitos o de bajo costo (Resend, Brevo, Azure Communication Services, entre otros). Se eligió **Azure Communication Services (correo)** por estas razones:

- La suscripción de Azure ya existía y ya había un recurso de correo creado con el dominio `gotogym.store` **verificado** (dominio, SPF, DKIM y DKIM2). Con otro proveedor habría hecho falta acceso a la cuenta de GoDaddy para verificar el dominio, y en ese momento no se tenía.
- Cobra por uso, con precios muy bajos por correo (confirmar en la página de precios de Azure).
- Funciona por SMTP, sin código propio.

Resend se descartó porque, sin dominio verificado, solo entrega al correo con el que se registra la cuenta.

## 3. Recursos en Azure

| Recurso | Nombre | Para qué |
|---|---|---|
| Communication Service | `acs-gotogym-prod` | Envía los correos y aloja las credenciales SMTP |
| Email Communication Service | `email-gotogym-prod` | Contiene el dominio verificado y las direcciones remitentes |
| Grupo de recursos | `rg-gotogym-app` | Contiene los dos anteriores. La aplicación está en otro grupo, `rg-gotogym-prime` |
| App Service | `gotogym-prime` | La tienda; recibe las variables de entorno |
| Aplicación de Microsoft Entra | `gotogym-smtp` | La identidad con la que la tienda se autentica ante el servicio de correo |

### 3.1 Comprobar que el dominio está listo

En `email-gotogym-prod` → **Provision domains**, el dominio `gotogym.store` debe mostrar **Verified** en las cuatro columnas: Domain, SPF, DKIM y DKIM2. En `acs-gotogym-prod` → **Email → Domains**, el mismo dominio debe aparecer **Connected**.

Si hubiera que crearlo desde cero, la pauta general de Azure es: crear un Email Communication Service, agregar el dominio personalizado, publicar en el DNS los registros TXT (verificación y SPF) y CNAME (DKIM y DKIM2) que Azure muestra, esperar a que pasen a Verified y conectar el dominio al Communication Service. Este paso no se ejecutó en esta sesión porque el dominio ya estaba listo; los detalles exactos los muestra el portal.

### 3.2 Dirección remitente

En `email-gotogym-prod` → Provision domains → `gotogym.store` → **Email services → MailFrom addresses** hay una sola dirección dada de alta: **`DoNotReply@gotogym.store`**.

Azure rechaza cualquier remitente que no esté dado de alta. Por eso la variable `DEFAULT_FROM_EMAIL` debe apuntar a una dirección de esa lista. El código trae por defecto `no-reply@gotogym.store`, que **no** está dada de alta; sin declarar la variable los envíos se rechazarían.

El nombre visible del remitente (hoy "DoNotReply") lo define el campo Display Name de esa dirección en Azure, no la variable. Para cambiarlo hay que dar de alta otra dirección con el nombre visible deseado y, solo después, apuntar `DEFAULT_FROM_EMAIL` a ella. Si el botón Add aparece atenuado, la cuenta no tiene permiso de edición sobre el recurso.

## 4. Credenciales SMTP

Azure no usa una contraseña simple: el servidor SMTP se autentica con una aplicación registrada en Microsoft Entra.

1. **Registrar la aplicación.** Portal → App registrations → New registration. Nombre `gotogym-smtp`, sin más cambios → Register.
2. **Crear el secreto.** En la aplicación → Manage → Certificates & secrets → Client secrets → New client secret. Descripción `smtp-tienda`, caducidad la más larga disponible. **Copiar la columna Value en ese momento** (no la columna Secret ID): después no se vuelve a mostrar. Ese valor es la contraseña SMTP.
3. **Anotar la fecha de caducidad** del secreto (ver sección 8).
4. **Crear el usuario SMTP.** `acs-gotogym-prod` → Email → **SMTP Usernames** → Add SMTP Username. Elegir la aplicación `gotogym-smtp`. Con tipo **Custom text** el nombre solo admite letras, números y los símbolos `.`, `-`, `_` y `/`; **no admite `@`**. Se usó `gotogym-tienda`. Al guardar debe quedar en estado **Ready to use**.

Si la creación falla por permisos, la persona que administra el directorio de Azure debe asignar el rol necesario (la pantalla lo ofrece al guardar) o hacerlo en Access control (IAM).

**Formato alternativo del usuario.** Si el nombre corto fallara con un error de autenticación, el usuario SMTP puede escribirse en el formato largo `<recurso>.<id-de-la-aplicación>.<id-del-directorio>`, con el nombre del recurso de comunicación, el Application (client) ID y el Directory (tenant) ID de la aplicación. No son secretos.

## 5. Variables de entorno de la aplicación

En el App Service `gotogym-prime` → Settings → **Environment variables → App settings → Add**. Pulsar **Apply** al terminar; la aplicación se reinicia.

| Variable | Valor | Notas |
|---|---|---|
| `EMAIL_HOST` | `smtp.azurecomm.net` | Sin esta variable los correos salen por consola y no llegan a nadie |
| `EMAIL_PORT` | `587` | |
| `EMAIL_USE_TLS` | `true` | |
| `EMAIL_HOST_USER` | `gotogym-tienda` | El usuario SMTP del paso 4 |
| `EMAIL_HOST_PASSWORD` | El valor del secreto de cliente | Solo se pega en Azure; nunca en el chat, el código ni archivos |
| `DEFAULT_FROM_EMAIL` | `GoToGym <DoNotReply@gotogym.store>` | Debe ser una dirección dada de alta (sección 3.2) |
| `SITIO_URL` | `https://shop.gotogym.store` | Los enlaces y las imágenes de los correos se arman con esta dirección. Sin ella apuntarían a `gotogym.store` |

Opcional: `EMAIL_TIMEOUT` (10 segundos por defecto), para que un servidor que no responde no deje colgado el trabajo de la aplicación.

Cambiar `SITIO_URL` exige reiniciar la aplicación.

## 6. Cómo se probó

1. **Envío real.** Desde SSH en el App Service (Herramientas de desarrollo → SSH):
   ```
   python gotogym/manage.py probar_correo tu-correo@dominio.com
   ```
   Debe responder `Correos enviados: 1 (remitente ...)` y el correo debe llegar a la **bandeja de entrada** (se comprobó que no cae en spam). Si el backend activo es el de consola, el comando lo avisa.
2. **Recuperación de contraseña** desde la tienda con una cuenta con un correo propio: llega el correo y el enlace abre `shop.gotogym.store`.
3. **Diseño de todos los correos**, sin enviar nada: `python manage.py previsualizar_correos` genera los 16 correos con datos de muestra (se crean en una transacción que se revierte, así que no queda nada en la base) y escribe HTML en `vista_previa_correos/`. Con `--enviar tucorreo@dominio.com` los manda además a una bandeja real; con `--idioma en` los del pedido salen en inglés. Para usarlo en local hace falta una base migrada.
4. **Pruebas automáticas.** La suite completa incluye pruebas de cada correo (contenido, idioma, imágenes, fallo del proveedor).

## 7. Cómo está hecho en el código

| Pieza | Dónde |
|---|---|
| Configuración SMTP y remitente | `gotogym/gotogym/settings.py` (sin `EMAIL_HOST` cae a consola) |
| Diseño y envío (utilidad compartida) | `gotogym/gotogym/correo.py` y `gotogym/gotogym/templates/correo/` |
| Correos del pedido | `gotogym/orders/correos.py` |
| Correos de afiliados | `gotogym/afiliados/correos.py` y `notify_commission_paid` en `afiliados/services.py` |
| Recuperación de contraseña | `accounts/templates/accounts/password_reset_email.html` (HTML) y `.txt` (texto), con la ruta en `accounts/urls.py` |
| Comandos | `accounts/management/commands/probar_correo.py` y `administracion/management/commands/previsualizar_correos.py` |

Cada correo se escribe una vez como contenido (párrafos, productos, totales, datos, botón) y de ahí salen el HTML y el texto. Los correos de pedido y de afiliados se ejecutan como tareas (`gotogym/tasks.py`, hoy dentro de la propia petición) que reciben solo un identificador. El correo de pedido recibido sale al crear el pedido y el de pedido confirmado cuando el pago queda aprobado.

## 8. Mantenimiento

### Renovar el secreto SMTP
El secreto de cliente caduca. **Al vencer, el correo deja de salir sin aviso**: solo se ve como un error de autenticación en el log. Antes de la fecha anotada:

1. En la aplicación `gotogym-smtp` → Certificates & secrets, crear un secreto nuevo y copiar su Value.
2. Reemplazar `EMAIL_HOST_PASSWORD` en el App Service y pulsar Apply.
3. Comprobar con `probar_correo`.
4. Eliminar el secreto viejo.

### Si el correo no llega
1. Ejecutar `probar_correo` y leer su mensaje. Un error de autenticación apunta a `EMAIL_HOST_USER` o al secreto (¿caducó?). Un rechazo del remitente apunta a `DEFAULT_FROM_EMAIL` (¿está dada de alta?).
2. Revisar el log de la aplicación: los fallos de envío se registran con el asunto y el pedido o la cuenta afectada.
3. Si el backend activo es el de consola, falta `EMAIL_HOST`.
4. Revisar los límites de Azure: el resumen del dominio muestra cuotas de 30 y 100 (probablemente por minuto y por hora; el rótulo estaba cortado). Un envío masivo, como los 16 correos de `previsualizar_correos --enviar`, cabe dentro del límite por minuto.

### Si los enlaces apuntan a otro dominio
Falta `SITIO_URL` o tiene el valor equivocado.

## 9. Pendientes conocidos

- **Registro SPF duplicado en GoDaddy.** El dominio publica dos registros SPF y solo puede haber uno. Debe quedar el que incluye `spf.protection.outlook.com` y `spf.azurecomm.net`, y borrarse el que solo incluye `spf.protection.outlook.com`. Quien tenga la cuenta de GoDaddy debe hacerlo.
- **Caducidad del secreto SMTP** sin anotar (sección 8).
- **Nombre visible del remitente** "DoNotReply" (sección 3.2); decisión de dejarlo así por ahora.
- **`support@gotogym.store`** aparece en la firma y es a donde remiten los correos para dudas. Confirmar que existe y que alguien la lee.
- **Los correos de pedido solo están traducidos al inglés.** En portugués salen en español.
- **Probar con pagos reales.** Los correos de pedido confirmado y cancelado dependen de que el pago pueda aprobarse; mientras la pasarela de pago no esté activa no se pueden ejercitar en producción.
- Las fotos de los productos en los correos se piden a `SITIO_URL`. Las que se suben desde el panel dependen de que los archivos subidos persistan entre despliegues.
