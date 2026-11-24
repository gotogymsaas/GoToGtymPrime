"""Tomar tareas de la cola, ejecutarlas y reprogramar las que fallan."""
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.module_loading import import_string

from .idempotencia import tarea_en_curso
from .models import EstadoTarea, TareaPendiente

logger = logging.getLogger(__name__)

# Espera antes del reintento n (1 minuto, 5 minutos, 30 minutos, 2 horas). Si
# hay mas intentos que esperas, se repite la ultima.
ESPERAS_SEGUNDOS = (60, 300, 1800, 7200)

_CORREO = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_NUMERO_LARGO = re.compile(r'\d{6,}')


def espera_para(intentos):
    """Segundos de espera tras el intento numero `intentos` (1 es el primero)."""
    return ESPERAS_SEGUNDOS[min(max(intentos, 1), len(ESPERAS_SEGUNDOS)) - 1]


def resumir_error(error):
    """Texto corto del error para guardarlo: la clase y el mensaje sin
    correos ni numeros largos (documentos, telefonos, tarjetas) y recortado."""
    mensaje = _NUMERO_LARGO.sub('[número]', _CORREO.sub('[correo]', str(error)))
    return f'{type(error).__name__}: {mensaje}'[:300]


def reclamar_siguiente(ahora):
    """Toma una tarea lista y la marca en curso, o devuelve None.

    La toma ocurre en una transaccion corta con `skip_locked`: dos
    trabajadores nunca reciben la misma fila. Una tarea que lleva en curso
    mas del tiempo maximo se da por perdida (el trabajador murio) y se
    recupera."""
    vencida = ahora - timedelta(seconds=settings.TAREAS_TIEMPO_MAXIMO_SEGUNDOS)
    with transaction.atomic():
        tarea = (
            TareaPendiente.objects.select_for_update(skip_locked=True)
            .filter(
                Q(estado=EstadoTarea.PENDIENTE, proximo_intento__lte=ahora)
                | Q(estado=EstadoTarea.EN_CURSO, iniciada__lt=vencida)
            )
            .order_by('proximo_intento', 'pk')
            .first()
        )
        if tarea is None:
            return None
        if tarea.estado == EstadoTarea.EN_CURSO and tarea.intentos >= tarea.maximo_intentos:
            tarea.estado = EstadoTarea.FALLIDA
            tarea.terminada = ahora
            tarea.ultimo_error = 'El trabajador se detuvo durante la ejecución.'
            tarea.save(update_fields=['estado', 'terminada', 'ultimo_error'])
            logger.error('La tarea %s (%s) se perdió en ejecución y agotó sus intentos.', tarea.pk, tarea.ruta)
            return None
        tarea.estado = EstadoTarea.EN_CURSO
        tarea.iniciada = ahora
        tarea.intentos += 1
        tarea.save(update_fields=['estado', 'iniciada', 'intentos'])
        return tarea


def ejecutar(tarea, reloj=timezone.now):
    """Ejecuta una tarea ya reclamada y registra el resultado."""
    argumentos = tarea.argumentos or {}
    try:
        funcion = import_string(tarea.ruta)
        with tarea_en_curso(tarea):
            funcion(*argumentos.get('args', []), **argumentos.get('kwargs', {}))
    except Exception as error:
        ahora = reloj()
        tarea.ultimo_error = resumir_error(error)
        if tarea.intentos >= tarea.maximo_intentos:
            tarea.estado = EstadoTarea.FALLIDA
            tarea.terminada = ahora
            # Error de nivel ERROR: Sentry lo recibe como evento.
            logger.exception('La tarea %s (%s) agotó sus %s intentos.', tarea.pk, tarea.ruta, tarea.intentos)
        else:
            espera = espera_para(tarea.intentos)
            tarea.estado = EstadoTarea.PENDIENTE
            tarea.proximo_intento = ahora + timedelta(seconds=espera)
            logger.warning(
                'La tarea %s (%s) falló en el intento %s; se reintenta en %s segundos.',
                tarea.pk, tarea.ruta, tarea.intentos, espera, exc_info=True,
            )
        tarea.save(update_fields=['estado', 'terminada', 'proximo_intento', 'ultimo_error'])
        return False
    tarea.estado = EstadoTarea.HECHA
    tarea.terminada = reloj()
    tarea.ultimo_error = ''
    tarea.save(update_fields=['estado', 'terminada', 'ultimo_error'])
    return True


def procesar_pendientes(ahora=None, limite=200, debe_parar=lambda: False):
    """Ejecuta las tareas listas hasta vaciar la cola, llegar a `limite` o que
    se pida parar. Devuelve cuantas ejecuto. Con `ahora` fijo (pruebas) el
    reloj no avanza."""
    reloj = (lambda: ahora) if ahora is not None else timezone.now
    procesadas = 0
    while procesadas < limite and not debe_parar():
        tarea = reclamar_siguiente(reloj())
        if tarea is None:
            break
        ejecutar(tarea, reloj)
        procesadas += 1
    return procesadas


def reintentar(tarea_id, ahora=None):
    """Devuelve una tarea fallida a la cola con sus intentos reiniciados. Las
    marcas de efecto ya aplicado se conservan. Devuelve True si cambio algo."""
    cambiadas = TareaPendiente.objects.filter(pk=tarea_id, estado=EstadoTarea.FALLIDA).update(
        estado=EstadoTarea.PENDIENTE, intentos=0, proximo_intento=ahora or timezone.now(),
        iniciada=None, terminada=None, ultimo_error='',
    )
    return cambiadas == 1
