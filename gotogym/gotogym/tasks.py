"""Tareas en segundo plano: una sola puerta para trabajo que no debe hacerse
dentro de la peticion web (correos, llamadas a proveedores externos).

Hoy no hay una cola desplegada, asi que el backend predeterminado (`sync`)
ejecuta la tarea en el mismo proceso. Lo importante es que quien encola ya
no depende de eso: cuando exista Celery, RQ o el sistema de tareas de Django,
se escribe un backend nuevo y se declara en `TASK_BACKEND`, sin tocar una sola
llamada a `enqueue`.

Para que eso sea posible, una tarea tiene que poder viajar por una cola:

- Es una funcion de modulo (no una lambda ni un metodo): se identifica por su
  ruta (`modulo.funcion`) y el trabajador la importa.
- Sus argumentos son datos simples (numeros, texto, listas, diccionarios),
  tipicamente ids. Nunca instancias de modelos: en la cola llegarian
  desactualizadas o no se podrian serializar.

`enqueue` lo comprueba desde el primer dia, para no descubrirlo el dia que se
instale la cola.

Un backend propio es una clase con `enqueue(ruta, args, kwargs)` y se declara
con su ruta completa: `TASK_BACKEND=mi_paquete.MiBackend`.
"""
import importlib
import json
import logging

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


class TaskError(ValueError):
    """La tarea no se puede encolar tal como esta escrita."""


class SyncBackend:
    """Ejecuta la tarea en el momento, en el mismo proceso.

    Un fallo se registra y no se propaga: la tarea ya es trabajo secundario
    (un aviso, una sincronizacion) y no debe romper la peticion que la origino.
    """

    def enqueue(self, ruta, args, kwargs):
        try:
            funcion = _importar(ruta)
            funcion(*args, **kwargs)
        except Exception:
            logger.exception('Fallo la tarea %s', ruta)


def _importar(ruta):
    modulo, _, nombre = ruta.rpartition('.')
    return getattr(importlib.import_module(modulo), nombre)


def _ruta_de(funcion):
    nombre = getattr(funcion, '__qualname__', '')
    if not callable(funcion) or '<lambda>' in nombre or '<locals>' in nombre or '.' in nombre:
        raise TaskError(
            'Una tarea debe ser una funcion definida a nivel de modulo '
            '(no una lambda, una funcion interna ni un metodo).'
        )
    return f'{funcion.__module__}.{nombre}'


def _backend():
    nombre = getattr(settings, 'TASK_BACKEND', 'sync')
    if nombre == 'sync':
        return SyncBackend()
    clase = _importar(nombre)
    return clase()


def enqueue(funcion, *args, after_commit=True, **kwargs):
    """Encola `funcion(*args, **kwargs)` para ejecutarse fuera de la peticion.

    Con `after_commit=True` (lo habitual) espera a que la transaccion en curso
    se confirme: si se revierte, la tarea no llega a ejecutarse. Fuera de una
    transaccion se ejecuta de inmediato.
    """
    ruta = _ruta_de(funcion)
    try:
        json.dumps([args, kwargs])
    except TypeError as error:
        raise TaskError(
            f'Los argumentos de {ruta} deben ser datos simples (ids, texto, numeros): {error}'
        ) from error

    def lanzar():
        _backend().enqueue(ruta, list(args), dict(kwargs))

    if after_commit:
        transaction.on_commit(lanzar)
    else:
        lanzar()
