"""Que un reintento no repita un efecto que ya ocurrio.

Un correo se envia y despues la tarea puede fallar por otra causa (la base de
datos, un corte). Al reintentarla, enviarlo de nuevo seria un duplicado. La
marca se guarda por ejecucion de tarea, no por argumentos: un hecho nuevo con
los mismos argumentos es otra tarea y si se envia.

Fuera del trabajador (backend `sync`, un comando, una prueba) no hay tarea en
curso y la funcion se ejecuta sin marca, exactamente como antes.
"""
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

logger = logging.getLogger(__name__)

_tarea_en_curso = ContextVar('tareas_tarea_en_curso', default=None)


@contextmanager
def tarea_en_curso(tarea):
    """Declara que `tarea` se esta ejecutando en este contexto."""
    token = _tarea_en_curso.set(tarea)
    try:
        yield
    finally:
        _tarea_en_curso.reset(token)


def efecto_unico(funcion):
    """Decorador para una tarea cuyo efecto externo no debe repetirse.

    La marca se escribe cuando la funcion termina sin error. Si la funcion
    falla, no hay marca y el reintento la ejecuta completa (por eso el efecto
    debe ser lo ultimo que hace). Si termina bien y despues se pierde el
    registro de la tarea (el trabajador muere, se corta la conexion), el
    reintento ve la marca y no repite el efecto. La unica ventana es un corte
    entre el efecto y la marca: el reintento lo repite (al menos una vez,
    nunca cero)."""
    nombre = f'{funcion.__module__}.{funcion.__qualname__}'

    @wraps(funcion)
    def envuelta(*args, **kwargs):
        tarea = _tarea_en_curso.get()
        if tarea is None:
            return funcion(*args, **kwargs)
        from .models import EfectoAplicado

        if EfectoAplicado.objects.filter(tarea=tarea, nombre=nombre).exists():
            logger.info('La tarea %s ya aplicó %s; se omite el reintento.', tarea.pk, nombre)
            return None
        resultado = funcion(*args, **kwargs)
        EfectoAplicado.objects.get_or_create(tarea=tarea, nombre=nombre)
        return resultado

    return envuelta
