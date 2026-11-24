"""El comando `trabajador`, el latido y `/readyz`."""
import signal
import threading
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from gotogym.tasks import enqueue

from tareas import latido
from tareas.management.commands import trabajador
from tareas.models import EstadoTarea, LatidoTrabajador, TareaPendiente, TareaPeriodica

LLAMADAS: list = []

BACKEND_BD = 'tareas.backend.DatabaseBackend'


def tarea_simple(identificador):
    LLAMADAS.append(identificador)


class _Base(TestCase):
    def setUp(self):
        LLAMADAS.clear()
        cache.clear()

    def correr(self, *argumentos):
        call_command('trabajador', *argumentos, stdout=StringIO())


@override_settings(TASK_BACKEND=BACKEND_BD)
class ComandoTests(_Base):
    def test_una_vez_procesa_lo_pendiente_y_sale(self):
        enqueue(tarea_simple, 1)
        enqueue(tarea_simple, 2)
        # Las periodicas del catalogo tambien tocan; se anulan para aislar la prueba.
        with patch('tareas.programador.encolar_periodicas'):
            self.correr('--una-vez')
        self.assertEqual(LLAMADAS, [1, 2])
        self.assertEqual(TareaPendiente.objects.filter(estado=EstadoTarea.HECHA).count(), 2)

    def test_una_vez_sincroniza_y_encola_las_periodicas(self):
        with patch('tareas.ejecucion.procesar_pendientes') as procesar:
            self.correr('--una-vez')
        self.assertEqual(TareaPeriodica.objects.count(), 7)
        self.assertEqual(TareaPendiente.objects.filter(clave_idempotencia__startswith='periodica:').count(), 7)
        procesar.assert_called_once()

    def test_dos_corridas_seguidas_no_repiten_las_periodicas_ni_las_tareas(self):
        enqueue(tarea_simple, 1)
        self.correr('--una-vez')
        antes = TareaPendiente.objects.count()
        self.correr('--una-vez')
        self.assertEqual(TareaPendiente.objects.count(), antes)
        self.assertEqual(LLAMADAS, [1])

    def test_escribe_el_latido_en_cada_ciclo(self):
        self.assertIsNone(latido.edad_del_latido())
        self.correr('--una-vez')
        self.assertLess(latido.edad_del_latido(), 5)

    def test_un_ciclo_que_falla_no_mata_al_trabajador(self):
        with patch('tareas.programador.encolar_periodicas', side_effect=RuntimeError('bd caida')):
            with self.assertLogs('tareas.management.commands.trabajador', level='ERROR'):
                self.correr('--una-vez')

    def test_sin_una_vez_repite_ciclos_hasta_recibir_la_senal_de_parada(self):
        ciclos = []

        def un_ciclo(self_, limite, parar):
            ciclos.append(1)
            if len(ciclos) == 3:
                parar.set()

        with patch.object(trabajador.Command, '_ciclo', un_ciclo):
            self.correr('--intervalo', '0')
        self.assertEqual(len(ciclos), 3)

    def test_el_apagado_limpio_termina_la_tarea_en_curso_y_no_toma_otra(self):
        for numero in range(3):
            enqueue(tarea_simple, numero)

        pedir_parada = {}
        original = trabajador.Command._instalar_senales

        def espiar(self_, parar):
            pedir_parada['evento'] = parar
            return original(self_, parar)

        def tarea_que_pide_parar(identificador):
            LLAMADAS.append(identificador)
            pedir_parada['evento'].set()  # como si llegara SIGTERM durante la tarea

        with patch.object(trabajador.Command, '_instalar_senales', espiar), \
                patch('tareas.test_trabajador.tarea_simple', tarea_que_pide_parar), \
                patch('tareas.programador.encolar_periodicas'):
            self.correr('--intervalo', '0')
        self.assertEqual(LLAMADAS, [0])
        self.assertEqual(TareaPendiente.objects.filter(estado=EstadoTarea.PENDIENTE).count(), 2)

    def test_instala_y_restaura_los_manejadores_de_senales(self):
        antes = signal.getsignal(signal.SIGINT)
        self.correr('--una-vez')
        self.assertEqual(signal.getsignal(signal.SIGINT), antes)

    def test_la_senal_de_parada_activa_el_evento(self):
        comando = trabajador.Command()
        parar = threading.Event()
        anteriores = comando._instalar_senales(parar)
        try:
            signal.raise_signal(signal.SIGINT)
            self.assertTrue(parar.is_set())
        finally:
            comando._restaurar_senales(anteriores)

    def test_sin_sigterm_en_la_plataforma_no_falla(self):
        comando = trabajador.Command()
        with patch.object(trabajador.signal, 'SIGTERM', None, create=True):
            anteriores = comando._instalar_senales(threading.Event())
        comando._restaurar_senales(anteriores)


class LatidoYReadyzTests(_Base):
    def test_la_edad_es_none_si_nunca_corrio(self):
        self.assertIsNone(latido.edad_del_latido())

    def test_la_edad_cuenta_desde_el_ultimo_ciclo(self):
        ahora = timezone.now()
        latido.registrar_latido(ahora - timedelta(seconds=42))
        self.assertEqual(latido.edad_del_latido(ahora), 42)
        latido.registrar_latido(ahora)
        self.assertEqual(LatidoTrabajador.objects.count(), 1)

    def test_readyz_informa_none_sin_latido_y_no_registra_error_con_sync(self):
        with self.assertNoLogs('tareas.latido', level='ERROR'):
            r = self.client.get('/readyz')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['worker_age_seconds'])

    def test_readyz_informa_la_antiguedad_del_latido(self):
        latido.registrar_latido(timezone.now() - timedelta(seconds=90))
        r = self.client.get('/readyz')
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()['worker_age_seconds'], 90)

    def test_con_sync_un_latido_viejo_no_registra_error(self):
        latido.registrar_latido(timezone.now() - timedelta(hours=2))
        with self.assertNoLogs('tareas.latido', level='ERROR'):
            self.client.get('/readyz')

    @override_settings(TASK_BACKEND=BACKEND_BD)
    def test_habilitado_con_latido_viejo_registra_error_pero_no_responde_503(self):
        latido.registrar_latido(timezone.now() - timedelta(seconds=301))
        with self.assertLogs('tareas.latido', level='ERROR'):
            r = self.client.get('/readyz')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'ready')

    @override_settings(TASK_BACKEND=BACKEND_BD)
    def test_habilitado_con_latido_reciente_no_registra_error(self):
        latido.registrar_latido(timezone.now() - timedelta(seconds=299))
        with self.assertNoLogs('tareas.latido', level='ERROR'):
            self.client.get('/readyz')

    @override_settings(TASK_BACKEND=BACKEND_BD)
    def test_habilitado_sin_latido_registra_error_una_vez_por_ventana(self):
        with self.assertLogs('tareas.latido', level='ERROR') as registro:
            self.client.get('/readyz')
            self.client.get('/readyz')
        self.assertEqual(len(registro.records), 1)

    def test_un_fallo_al_leer_el_latido_no_tumba_readyz(self):
        with patch('gotogym.views.revisar_latido', side_effect=RuntimeError('tabla ausente')):
            with self.assertLogs('gotogym.views', level='ERROR'):
                r = self.client.get('/readyz')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()['worker_age_seconds'])
