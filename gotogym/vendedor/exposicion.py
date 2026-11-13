"""Quien ve el vendedor.

Dos condiciones tienen que cumplirse para que Quantum Coach se muestre en la
tienda (`asistente_activo`):

1. `VENDEDOR_ENABLED`: corte tecnico de emergencia, por configuracion del
   despliegue. Encendido por defecto.
2. Que el administrador lo haya habilitado con el interruptor "Habilitar
   Coach" del panel (`PanelSettings.coach_enabled`). Es la decision de negocio
   y se cambia sin desplegar.

Que se muestre no quiere decir que haya una IA detras. Sin servicio
configurado (`COACH_API_URL`, o el Coach simulado solo en desarrollo y
pruebas) el Coach se ve igual y contesta que la IA no esta disponible por
ahora (`coach_configurado`). Asi quien visita la tienda sabe que existe y que
volvera, en vez de no enterarse.

Con `VENDEDOR_ROLLOUT_PERCENT` por debajo de 100 solo lo ve ese porcentaje de
visitantes, elegido de forma estable a partir del hash del visitante: la misma
persona ve siempre lo mismo y quien no lo ve forma un grupo de control con el
que comparar.

Para analizar un experimento no hace falta guardar el grupo: se recalcula con
`grupo_del_visitante(sesion)` para cualquier evento, incluido `order_created`,
porque todos llevan el mismo hash de visitante en `sesion`.

Con un porcentaje parcial, decidir el grupo exige un identificador de
visitante, y crearlo abre la sesion (cookie tecnica de sesion) aunque aun no
haya carrito. Con 100 % no hace falta y no se crea nada.
"""
import hashlib

from analitica.services import hash_visitante
from django.conf import settings
from gotogym.ajustes_tienda import coach_habilitado

GRUPO_VENDEDOR = 'vendedor'
GRUPO_CONTROL = 'control'


def grupo_del_visitante(hash_del_visitante, porcentaje=None):
    """`vendedor` o `control` para un hash de visitante (el de analitica)."""
    if porcentaje is None:
        porcentaje = settings.VENDEDOR_ROLLOUT_PERCENT
    semilla = f'vendedor-exposicion:{hash_del_visitante}'.encode()
    cubo = int(hashlib.sha256(semilla).hexdigest()[:8], 16) % 100
    return GRUPO_VENDEDOR if cubo < porcentaje else GRUPO_CONTROL


def coach_configurado():
    """Hay a quien preguntar: un servicio de IA o el Coach simulado."""
    return bool(settings.COACH_API_URL) or settings.VENDEDOR_COACH_SIMULADO


def asistente_activo(request=None):
    """El Coach se muestra en la tienda, sin mirar a cada visitante. La
    condicion barata va primero: la otra consulta la base de datos (una vez
    por peticion si se pasa `request`)."""
    return bool(settings.VENDEDOR_ENABLED) and coach_habilitado(request)


def coach_en_servicio():
    """Ademas de mostrarse, hay una IA que recibe los mensajes. Solo entonces
    se envian datos a un servicio externo, y por eso solo entonces las
    politicas de privacidad tienen algo que declarar."""
    return asistente_activo() and coach_configurado()


def visible_para(request):
    if not asistente_activo(request):
        return False
    porcentaje = settings.VENDEDOR_ROLLOUT_PERCENT
    if porcentaje >= 100:
        return True
    if porcentaje <= 0:
        return False
    return grupo_del_visitante(hash_visitante(request), porcentaje) == GRUPO_VENDEDOR
