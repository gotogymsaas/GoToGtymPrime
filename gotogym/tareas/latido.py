"""El latido del trabajador: cuando termino su ultimo ciclo."""
import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import LatidoTrabajador

logger = logging.getLogger(__name__)

# Pasado este tiempo sin ciclos, un trabajador habilitado se considera caido.
LATIDO_MAXIMO_SEGUNDOS = 300


def registrar_latido(ahora=None):
    LatidoTrabajador.objects.update_or_create(pk=1, defaults={'ultimo_ciclo': ahora or timezone.now()})


def edad_del_latido(ahora=None):
    """Segundos desde el ultimo ciclo del trabajador, o None si nunca corrio."""
    ultimo = LatidoTrabajador.objects.filter(pk=1).values_list('ultimo_ciclo', flat=True).first()
    if ultimo is None:
        return None
    return max(0, int(((ahora or timezone.now()) - ultimo).total_seconds()))


def trabajador_habilitado():
    return getattr(settings, 'TASK_BACKEND', 'sync') != 'sync'


def revisar_latido(ahora=None):
    """Devuelve la edad del latido para informarla y, si el backend esta
    habilitado y el trabajador lleva mas de cinco minutos sin latir, deja un
    error en el log (una vez cada cinco minutos, no en cada consulta del
    health check)."""
    edad = edad_del_latido(ahora)
    if trabajador_habilitado() and (edad is None or edad > LATIDO_MAXIMO_SEGUNDOS):
        try:
            primera_vez = cache.add('tareas_latido_aviso', 1, LATIDO_MAXIMO_SEGUNDOS)
        except Exception:
            primera_vez = True
        if primera_vez:
            logger.error(
                'El trabajador de tareas no late: %s.',
                'nunca ha corrido' if edad is None else f'último ciclo hace {edad} segundos',
            )
    return edad
