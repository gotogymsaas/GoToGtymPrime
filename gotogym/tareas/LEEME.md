# Tareas en segundo plano

App `tareas`: una cola de tareas guardada en la base de datos y un programador de
tareas periódicas, sin infraestructura nueva. **Está apagada por defecto**: mientras
`TASK_BACKEND` valga `sync` (el valor por defecto, también en pruebas) nada cambia,
las tareas se ejecutan en la misma petición como siempre.

## Cómo funciona

- `gotogym.tasks.enqueue(funcion, *args)` es la única puerta. Con
  `TASK_BACKEND=tareas.backend.DatabaseBackend` inserta una fila `TareaPendiente`
  **dentro de la transacción en curso** (no con `transaction.on_commit`): si el
  negocio revierte, la tarea no existe; si confirma, la tarea ya está guardada y no
  se pierde si el proceso muere justo después.
- `python manage.py trabajador` toma las tareas listas (`select_for_update(skip_locked=True)`),
  las ejecuta y, si fallan, las reprograma con espera creciente: 1 min, 5 min, 30 min,
  2 h. Tras `TAREAS_MAX_INTENTOS` (5) la tarea queda **fallida**, se registra con
  `logger.exception` (Sentry la recibe como evento) y aparece en el panel.
- Cada ciclo también encola las tareas periódicas que tocan y escribe un latido
  (`LatidoTrabajador`). Varios trabajadores a la vez son seguros.
- Una tarea "en curso" más de `TAREAS_TIEMPO_MAXIMO_SEGUNDOS` (900) se da por perdida
  (el trabajador murió) y otra corrida la recupera.
- El error guardado en la tarea no lleva correos ni números largos y se recorta a 300
  caracteres. Los argumentos de la tarea (ids, a veces un texto) no se muestran en el panel.

### Tareas periódicas (catálogo en `programador.py`)

| Nombre | Qué ejecuta | Cada |
|---|---|---|
| `cancelar_pedidos_vencidos` | `orders.services.cancel_expired_orders` | 1 h |
| `emitir_facturas_pendientes` | comando `emitir_facturas_pendientes` | 15 min |
| `confirmar_comisiones` | `afiliados.services.confirmar_comisiones_vencidas` | 1 día |
| `aplicar_bajas_de_afiliados` | `afiliados.services.aplicar_bajas_vencidas` | 1 día |
| `purgar_analitica` | comando `purgar_analitica` | 1 día |
| `limpiar_sesiones` | comando `clearsessions` | 1 día |
| `purgar_tareas_terminadas` | borra tareas hechas o fallidas con más de `TAREAS_RETENCION_DIAS` (30) días | 1 día |

El trabajador sincroniza el catálogo con la tabla `TareaPeriodica` al arrancar. Para
apagar una tarea periódica, poner `activa=False` en su fila (se respeta al sincronizar).
Si la corrida anterior de una tarea sigue en cola, no se encola otra encima.

### Variables de entorno (todas opcionales)

| Variable | Defecto | Uso |
|---|---|---|
| `TASK_BACKEND` | `sync` | `tareas.backend.DatabaseBackend` para activar la cola |
| `TAREAS_MAX_INTENTOS` | `5` | Intentos antes de dar una tarea por fallida |
| `TAREAS_INTERVALO_SEGUNDOS` | `10` | Espera entre ciclos del trabajador |
| `TAREAS_TIEMPO_MAXIMO_SEGUNDOS` | `900` | Tiempo tras el que una tarea "en curso" se da por perdida |
| `TAREAS_RETENCION_DIAS` | `30` | Días que se conservan las tareas terminadas |

## Activación (requiere acceso a Azure; no se ha hecho)

Orden seguro. El paso 1 es lo que evita perder tareas: con la variable puesta y sin
trabajador, las tareas se acumulan sin ejecutarse (los correos no saldrían).

1. **Migrar** la base de datos (`python manage.py migrate`; crea las tablas de `tareas`).
2. **Lanzar el trabajador** antes de activar la variable. Dos opciones:
   - WebJob continuo del App Service con el comando
     `python manage.py trabajador` (desde la carpeta `gotogym/`, con el mismo entorno
     virtual y las mismas variables que la aplicación).
   - O un proceso junto a gunicorn, lanzado desde `startup.sh` antes de `exec gunicorn`:
     `python manage.py trabajador &`. Ojo: si gunicorn se reinicia sin reiniciar el
     contenedor, ese proceso no se relanza solo; el WebJob continuo es más robusto.
   - Alternativa sin proceso permanente: una tarea programada que ejecute
     `python manage.py trabajador --una-vez` cada minuto. Las periódicas llegarán con
     ese retraso.
3. **Verificar** que corre: `/readyz` debe mostrar `worker_age_seconds` menor a unos
   10 segundos (con `--una-vez` programado, menor al periodo).
4. **Activar** `TASK_BACKEND=tareas.backend.DatabaseBackend` en la configuración de
   la aplicación y reiniciarla.
5. Revisar en el panel (`/admin-panel/tareas/`) que no haya tareas fallidas y que las
   periódicas muestren su última ejecución.
6. **Esperar una semana estable** antes de retirar las llamadas en línea de
   `cancel_expired_orders` en las vistas del checkout y del panel y la de
   `_poner_al_dia_afiliados`. Esas llamadas siguen ahí a propósito: son inofensivas
   (las funciones son idempotentes) y cubren una caída del trabajador.

`readyz` nunca responde 503 por el trabajador. Si el backend está habilitado y el
latido supera 5 minutos (o no existe), registra un error (una vez cada 5 minutos).

### Volver atrás

1. Poner `TASK_BACKEND=sync` y reiniciar la aplicación: desde ese momento `enqueue`
   vuelve a ejecutar en el momento.
2. Las tareas que quedaron pendientes en la tabla no se ejecutan solas. Dejar el
   trabajador corriendo hasta que la cola se vacíe (panel de tareas) y entonces pararlo,
   o ejecutar `python manage.py trabajador --una-vez` a mano para vaciarla.
3. Las tablas de `tareas` pueden quedar; no estorban.

### Permisos del panel

La pantalla está en `/admin-panel/tareas/`. Ver exige `tareas.view_tareapendiente` y
reintentar `tareas.retry_tarea` (los superusuarios pasan). Sin permiso responde 403. Hay
que asignarlos a un Grupo o usuario; no forman parte del paquete automático de
"Administrador" (`administracion/permissions.py`). El enlace en el menú lateral del panel
(`administracion/base.html`) tampoco existe todavía: la pantalla se abre por su dirección.

## Idempotencia: qué es seguro reintentar

Un reintento ocurre cuando la tarea falla (se vuelve a ejecutar completa), cuando el
trabajador muere en medio, o cuando alguien pulsa "Reintentar" en el panel.

Los correos llevan el decorador `tareas.idempotencia.efecto_unico`: al terminar sin
error guardan una marca (`EfectoAplicado`) ligada a **esa tarea**. Si la misma tarea se
vuelve a ejecutar (porque se perdió el registro de su resultado, o por "Reintentar"),
ve la marca y no reenvía. Un hecho nuevo con los mismos argumentos (una segunda baja del
mismo afiliado, un reenvío de tarjeta desde el panel) es otra tarea y sí se envía.
Para que el reintento funcione, un fallo de envío ya **se propaga** desde `_enviar`
(antes solo se registraba): con `sync` lo sigue capturando `SyncBackend`, igual que antes.

| Tarea | Segura de reintentar | Cómo |
|---|---|---|
| `orders.correos.pedido_recibido`, `pedido_confirmado`, `pedido_enviado`, `pedido_cancelado`, `tarjeta_regalo_comprada` | Sí | `efecto_unico`; el envío es lo último que hacen |
| `orders.correos.tarjeta_regalo_para_destinatario` | Sí | `efecto_unico`; además registra `sent_at` solo si salió. El reenvío manual del panel crea otra tarea y sí reenvía |
| `afiliados.correos.*` (solicitud, aprobado, rechazado, baja solicitada/efectiva, terminación, validación extendida, cambio de tasa, aviso general) | Sí | `efecto_unico` |
| `orders.facturacion.emitir_factura` | Sí | Idempotente por diseño: estado propio de la factura (`Invoice`), reclamo atómico; no lanza excepciones, así que los fallos de Alegra los reintenta la tarea periódica `emitir_facturas_pendientes` |
| `afiliados.services.notify_commission_paid` | No se reintenta | Captura sus propios errores y no los propaga, así que un fallo de correo se pierde (no se duplica). Para reintentarlo habría que decorarla con `efecto_unico` y propagar el fallo (cambio en `afiliados/services.py`) |
| Tareas periódicas | Sí | Cada función es idempotente (el comando de facturas, la purga, la cancelación y las comisiones se pueden ejecutar de más) |

Limitación honesta: si el proceso muere exactamente entre enviar el correo y escribir
la marca, el reintento lo envía otra vez (al menos una vez, nunca cero).

Una tarea nueva con efectos externos debe: ser una función de módulo con argumentos
simples, hacer el efecto como último paso, propagar sus fallos y, si repetir el efecto
es dañino, usar `@efecto_unico`.
