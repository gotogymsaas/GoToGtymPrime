"""Estado de la conversacion del visitante, guardado en su sesion.

El servidor es quien emite el identificador de conversacion y cuenta los
turnos: el valor que el navegador conserva en `sessionStorage` sirve solo para
que el panel recuerde el historial que ya mostro, y no se acepta como
identificador. Asi un cliente no puede reutilizar la conversacion de otro ni
saltarse el tope de turnos inventando identificadores nuevos.

No se guarda texto de mensajes: solo el identificador y el numero de turnos.

La espera que pide el Coach tras un error no vive aqui: Django no guarda la
sesion en las respuestas 5xx, que son justo las que informan de un fallo, y
una espera ligada a la sesion se saltaria borrando la cookie. Esta en la
cache, por usuario o IP (ver `views`).
"""
import time
import uuid

CLAVE_SESION = 'vendedor_conversacion'

# Tras tanto tiempo sin escribir, la siguiente vez empieza otra conversacion.
INACTIVIDAD_SEGUNDOS = 30 * 60


def _nueva(ahora):
    return {'id': f'shop-{uuid.uuid4()}', 'turnos': 0, 'ultimo': ahora}


def obtener(sesion, ahora=None, reiniciar=False):
    """Conversacion vigente, o una nueva si no hay, caduco o se pide otra."""
    ahora = time.time() if ahora is None else ahora
    estado = sesion.get(CLAVE_SESION)
    caducada = bool(estado) and ahora - estado.get('ultimo', 0) > INACTIVIDAD_SEGUNDOS
    if not estado or reiniciar or caducada:
        estado = _nueva(ahora)
        sesion[CLAVE_SESION] = estado
    return estado


def turno_completado(sesion, estado, ahora=None):
    ahora = time.time() if ahora is None else ahora
    estado['turnos'] = estado.get('turnos', 0) + 1
    estado['ultimo'] = ahora
    sesion[CLAVE_SESION] = estado
