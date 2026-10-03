"""Puerta unica de tareas en segundo plano (`gotogym.tasks`)."""
from django.db import transaction
from django.test import TestCase, override_settings

from gotogym.tasks import SyncBackend, TaskError, enqueue

EJECUTADAS: list = []
RECIBIDAS_POR_LA_COLA: list = []


def tarea_de_prueba(identificador, nota=''):
    EJECUTADAS.append((identificador, nota))


def tarea_que_falla():
    raise RuntimeError('fallo a proposito')


class ColaDePrueba:
    """Backend propio: en vez de ejecutar, anota lo que recibiria una cola real."""

    def enqueue(self, ruta, args, kwargs):
        RECIBIDAS_POR_LA_COLA.append((ruta, args, kwargs))


class EncolarTests(TestCase):
    def setUp(self):
        EJECUTADAS.clear()
        RECIBIDAS_POR_LA_COLA.clear()

    def test_el_backend_predeterminado_ejecuta_en_el_momento(self):
        enqueue(tarea_de_prueba, 7, nota='hola', after_commit=False)
        self.assertEqual(EJECUTADAS, [(7, 'hola')])

    def test_un_fallo_de_la_tarea_se_registra_y_no_rompe_a_quien_encola(self):
        with self.assertLogs('gotogym.tasks', level='ERROR'):
            enqueue(tarea_que_falla, after_commit=False)

    def test_espera_a_que_la_transaccion_se_confirme(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            enqueue(tarea_de_prueba, 1)
            self.assertEqual(EJECUTADAS, [])  # todavia no
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertEqual(EJECUTADAS, [(1, '')])

    def test_si_la_transaccion_se_revierte_la_tarea_no_se_ejecuta(self):
        try:
            with transaction.atomic():
                enqueue(tarea_de_prueba, 2)
                raise RuntimeError('revierte')
        except RuntimeError:
            pass
        self.assertEqual(EJECUTADAS, [])

    @override_settings(TASK_BACKEND='gotogym.test_tasks.ColaDePrueba')
    def test_un_backend_propio_recibe_la_ruta_y_los_argumentos(self):
        enqueue(tarea_de_prueba, 9, nota='x', after_commit=False)
        self.assertEqual(
            RECIBIDAS_POR_LA_COLA,
            [('gotogym.test_tasks.tarea_de_prueba', [9], {'nota': 'x'})],
        )
        self.assertEqual(EJECUTADAS, [])  # la cola decide cuando ejecutar

    def test_rechaza_lo_que_no_podria_viajar_por_una_cola(self):
        with self.assertRaises(TaskError):
            enqueue(lambda: None, after_commit=False)
        with self.assertRaises(TaskError):
            enqueue(object().__class__.__init__, after_commit=False)
        with self.assertRaises(TaskError):
            enqueue(tarea_de_prueba, object(), after_commit=False)  # no es un dato simple

    def test_el_backend_sync_se_puede_usar_directamente(self):
        SyncBackend().enqueue('gotogym.test_tasks.tarea_de_prueba', [5], {})
        self.assertEqual(EJECUTADAS, [(5, '')])
