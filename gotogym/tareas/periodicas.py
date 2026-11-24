"""Funciones de las tareas periodicas que no existen como funcion en otra app
(son comandos de gestion) o que pertenecen a esta app. Reutilizan el comando
tal cual, sin copiar su logica."""
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from .models import EstadoTarea, TareaPendiente


def _ejecutar_comando(nombre, *args):
    call_command(nombre, *args, stdout=StringIO(), stderr=StringIO())


def emitir_facturas_pendientes():
    _ejecutar_comando('emitir_facturas_pendientes')


def purgar_analitica():
    _ejecutar_comando('purgar_analitica')


def limpiar_sesiones():
    _ejecutar_comando('clearsessions')


def purgar_tareas_terminadas(ahora=None):
    """Borra las tareas hechas o fallidas que terminaron hace mas de
    `TAREAS_RETENCION_DIAS` (con sus marcas de efecto). Devuelve cuantas."""
    limite = (ahora or timezone.now()) - timedelta(days=settings.TAREAS_RETENCION_DIAS)
    borradas, _ = TareaPendiente.objects.filter(
        estado__in=[EstadoTarea.HECHA, EstadoTarea.FALLIDA], terminada__lt=limite,
    ).delete()
    return borradas
