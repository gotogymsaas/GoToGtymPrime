"""Tareas periodicas: el catalogo vive en codigo y se sincroniza con la tabla.

Las rutas son cadenas que el trabajador resuelve con `import_string` al
ejecutar: asi `tareas` no importa ninguna app (la regla de capas lo impide) y
un cambio de nombre en una app se nota en la ejecucion, no al arrancar.
"""
import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import EstadoTarea, TareaPendiente, TareaPeriodica

logger = logging.getLogger(__name__)

HORA = 3600
DIA = 24 * HORA

# (nombre, ruta de la funcion, intervalo en segundos). Cada funcion es
# idempotente: se puede ejecutar de mas sin efectos duplicados.
CATALOGO = (
    ('cancelar_pedidos_vencidos', 'orders.services.cancel_expired_orders', HORA),
    ('emitir_facturas_pendientes', 'tareas.periodicas.emitir_facturas_pendientes', 15 * 60),
    ('confirmar_comisiones', 'afiliados.services.confirmar_comisiones_vencidas', DIA),
    ('aplicar_bajas_de_afiliados', 'afiliados.services.aplicar_bajas_vencidas', DIA),
    ('purgar_analitica', 'tareas.periodicas.purgar_analitica', DIA),
    ('limpiar_sesiones', 'tareas.periodicas.limpiar_sesiones', DIA),
    ('purgar_tareas_terminadas', 'tareas.periodicas.purgar_tareas_terminadas', DIA),
)


def sincronizar_catalogo():
    """Deja la tabla igual al catalogo: crea las nuevas, actualiza ruta e
    intervalo y desactiva las que ya no estan. No toca `activa` ni
    `ultima_ejecucion` de las que siguen (apagar una a mano se respeta)."""
    nombres = []
    for nombre, ruta, intervalo in CATALOGO:
        nombres.append(nombre)
        TareaPeriodica.objects.update_or_create(
            nombre=nombre, defaults={'ruta': ruta, 'intervalo_segundos': intervalo},
        )
    TareaPeriodica.objects.exclude(nombre__in=nombres).update(activa=False)


def _le_toca(periodica, ahora):
    if periodica.ultima_ejecucion is None:
        return True
    return ahora >= periodica.ultima_ejecucion + timedelta(seconds=periodica.intervalo_segundos)


def encolar_periodicas(ahora=None):
    """Encola las tareas periodicas que ya tocan. Devuelve sus nombres.

    Es seguro con varios trabajadores: la ultima ejecucion se reclama con una
    actualizacion condicionada al valor leido, y solo quien la gana encola. Si
    la corrida anterior de la misma tarea sigue pendiente o en curso (tarda
    mas que su intervalo) no se encola otra encima."""
    ahora = ahora or timezone.now()
    encoladas = []
    for periodica in TareaPeriodica.objects.filter(activa=True):
        if not _le_toca(periodica, ahora):
            continue
        prefijo = f'periodica:{periodica.nombre}:'
        sigue_en_cola = TareaPendiente.objects.filter(
            clave_idempotencia__startswith=prefijo,
            estado__in=[EstadoTarea.PENDIENTE, EstadoTarea.EN_CURSO],
        ).exists()
        if sigue_en_cola:
            continue
        try:
            with transaction.atomic():
                reclamada = TareaPeriodica.objects.filter(
                    pk=periodica.pk, ultima_ejecucion=periodica.ultima_ejecucion,
                ).update(ultima_ejecucion=ahora)
                if not reclamada:
                    continue
                TareaPendiente.objects.create(
                    ruta=periodica.ruta,
                    argumentos={'args': [], 'kwargs': {}},
                    clave_idempotencia=f'{prefijo}{ahora.isoformat()}',
                    proximo_intento=ahora,
                )
        except IntegrityError:
            logger.warning('La tarea periódica %s ya estaba encolada para este momento.', periodica.nombre)
            continue
        encoladas.append(periodica.nombre)
    return encoladas
