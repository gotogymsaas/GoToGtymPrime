"""Trabajador de tareas en segundo plano.

Cada ciclo encola las tareas periodicas que tocan, ejecuta las tareas listas y
escribe el latido. Sin `--una-vez` repite el ciclo hasta recibir SIGTERM o
SIGINT; entonces termina la tarea en curso y sale.

Se puede lanzar como WebJob continuo, junto a gunicorn, o con `--una-vez` desde
una tarea programada. Varios trabajadores a la vez son seguros.
"""
import logging
import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from tareas import ejecucion, programador
from tareas.latido import registrar_latido

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ejecuta las tareas en segundo plano y las tareas periódicas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--una-vez', action='store_true',
            help='Procesa lo que haya y sale (para un WebJob o una tarea programada).',
        )
        parser.add_argument(
            '--intervalo', type=float, default=None,
            help='Segundos de espera entre ciclos (por defecto TAREAS_INTERVALO_SEGUNDOS).',
        )
        parser.add_argument(
            '--limite', type=int, default=200,
            help='Máximo de tareas por ciclo (200 por defecto).',
        )

    def handle(self, *args, una_vez, intervalo, limite, **options):
        intervalo = settings.TAREAS_INTERVALO_SEGUNDOS if intervalo is None else intervalo
        parar = threading.Event()
        anteriores = self._instalar_senales(parar)
        try:
            programador.sincronizar_catalogo()
            logger.info('Trabajador de tareas iniciado (intervalo %s s).', intervalo)
            while not parar.is_set():
                self._ciclo(limite, parar)
                if una_vez:
                    break
                parar.wait(intervalo)
            logger.info('Trabajador de tareas detenido.')
        finally:
            self._restaurar_senales(anteriores)

    def _ciclo(self, limite, parar):
        """Un fallo del ciclo se registra y no mata al trabajador: si la base
        de datos parpadea, el siguiente ciclo ya funciona."""
        try:
            close_old_connections()
            programador.encolar_periodicas()
            ejecucion.procesar_pendientes(limite=limite, debe_parar=parar.is_set)
            registrar_latido()
        except Exception:
            logger.exception('Falló un ciclo del trabajador de tareas.')

    def _instalar_senales(self, parar):
        anteriores = {}

        def pedir_parada(numero, marco):
            parar.set()

        # SIGTERM no existe en todas las plataformas (Windows) y solo se puede
        # instalar un manejador desde el hilo principal.
        for nombre in ('SIGTERM', 'SIGINT', 'SIGBREAK'):
            numero = getattr(signal, nombre, None)
            if numero is None:
                continue
            try:
                anteriores[numero] = signal.signal(numero, pedir_parada)
            except (ValueError, OSError):
                continue
        return anteriores

    def _restaurar_senales(self, anteriores):
        for numero, manejador in anteriores.items():
            try:
                signal.signal(numero, manejador)
            except (ValueError, OSError, TypeError):
                continue
