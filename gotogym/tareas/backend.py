"""Backend de `gotogym.tasks` que guarda las tareas en la base de datos.

Se activa con `TASK_BACKEND=tareas.backend.DatabaseBackend`. No necesita
infraestructura nueva: un proceso (`manage.py trabajador`) toma las filas y
las ejecuta.
"""
from django.conf import settings

from .models import TareaPendiente


class DatabaseBackend:
    # `gotogym.tasks.enqueue` normalmente espera al commit con
    # `transaction.on_commit` antes de llamar al backend. Aqui no sirve: si el
    # proceso muere entre el commit y el callback, la tarea se pierde sin
    # dejar rastro. Insertar la fila dentro de la transaccion del negocio da
    # las dos garantias a la vez: si el commit se revierte la fila tambien
    # (la tarea no existe), y si se confirma la fila ya esta (no se pierde).
    dentro_de_la_transaccion = True

    def enqueue(self, ruta, args, kwargs):
        TareaPendiente.objects.create(
            ruta=ruta,
            argumentos={'args': list(args), 'kwargs': dict(kwargs)},
            maximo_intentos=settings.TAREAS_MAX_INTENTOS,
        )
