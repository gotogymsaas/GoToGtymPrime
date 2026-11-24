"""La cola en base de datos: encolar, ejecutar, reintentar, no duplicar."""
from datetime import timedelta

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from gotogym.tasks import SyncBackend, _backend, enqueue

from tareas import ejecucion
from tareas.backend import DatabaseBackend
from tareas.idempotencia import efecto_unico
from tareas.models import EfectoAplicado, EstadoTarea, TareaPendiente

LLAMADAS: list = []
ESTADO = {'falla': False, 'despues_del_efecto': False}

BACKEND_BD = 'tareas.backend.DatabaseBackend'


def tarea_simple(identificador, nota=''):
    LLAMADAS.append((identificador, nota))


def tarea_que_falla():
    LLAMADAS.append('intento')
    raise RuntimeError('no se pudo enviar a persona@example.com con el documento 1234567890')


def tarea_inestable():
    LLAMADAS.append('intento')
    if ESTADO['falla']:
        raise OSError('servidor caido')


@efecto_unico
def tarea_con_efecto(identificador):
    LLAMADAS.append(('efecto', identificador))
    if ESTADO['despues_del_efecto']:
        raise OSError('cae despues de enviar')


class _Base(TestCase):
    def setUp(self):
        LLAMADAS.clear()
        ESTADO.update(falla=False, despues_del_efecto=False)
        # Un segundo despues de ahora: lo encolado en la prueba ya esta listo.
        self.t0 = timezone.now() + timedelta(seconds=1)


@override_settings(TASK_BACKEND=BACKEND_BD)
class EncolarTests(_Base):
    def test_el_backend_se_elige_por_configuracion(self):
        self.assertIsInstance(_backend(), DatabaseBackend)

    def test_encolar_guarda_una_fila_sin_ejecutar(self):
        enqueue(tarea_simple, 7, nota='hola')
        tarea = TareaPendiente.objects.get()
        self.assertEqual(tarea.ruta, 'tareas.test_cola.tarea_simple')
        self.assertEqual(tarea.argumentos, {'args': [7], 'kwargs': {'nota': 'hola'}})
        self.assertEqual(tarea.estado, EstadoTarea.PENDIENTE)
        self.assertEqual(LLAMADAS, [])

    def test_la_fila_se_inserta_dentro_de_la_transaccion_en_curso(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            enqueue(tarea_simple, 1)
            self.assertEqual(TareaPendiente.objects.count(), 1)
        # No queda nada esperando al commit: la fila ya forma parte de la transaccion.
        self.assertEqual(callbacks, [])

    def test_si_la_transaccion_se_revierte_la_tarea_no_existe(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                enqueue(tarea_simple, 1)
                raise RuntimeError('el negocio fallo')
        self.assertEqual(TareaPendiente.objects.count(), 0)

    def test_los_argumentos_siguen_validandose(self):
        from gotogym.tasks import TaskError

        with self.assertRaises(TaskError):
            enqueue(tarea_simple, object())
        self.assertEqual(TareaPendiente.objects.count(), 0)

    def test_el_maximo_de_intentos_viene_de_la_configuracion(self):
        with override_settings(TAREAS_MAX_INTENTOS=3):
            enqueue(tarea_simple, 1)
        self.assertEqual(TareaPendiente.objects.get().maximo_intentos, 3)


class SyncNoCambiaTests(_Base):
    """Con `sync` (el valor por defecto) `enqueue` se comporta como siempre."""

    def test_el_backend_predeterminado_es_sync(self):
        self.assertIsInstance(_backend(), SyncBackend)

    def test_sigue_esperando_al_commit_y_no_toca_la_tabla(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            enqueue(tarea_simple, 3)
        self.assertEqual(LLAMADAS, [])
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertEqual(LLAMADAS, [(3, '')])
        self.assertEqual(TareaPendiente.objects.count(), 0)

    def test_un_fallo_se_registra_y_no_se_propaga(self):
        with self.assertLogs('gotogym.tasks', level='ERROR'):
            enqueue(tarea_que_falla, after_commit=False)
        self.assertEqual(TareaPendiente.objects.count(), 0)

    def test_el_efecto_unico_no_hace_nada_fuera_del_trabajador(self):
        enqueue(tarea_con_efecto, 5, after_commit=False)
        enqueue(tarea_con_efecto, 5, after_commit=False)
        self.assertEqual(LLAMADAS, [('efecto', 5), ('efecto', 5)])
        self.assertEqual(EfectoAplicado.objects.count(), 0)


@override_settings(TASK_BACKEND=BACKEND_BD)
class EjecucionTests(_Base):
    def test_una_tarea_se_ejecuta_con_sus_argumentos_y_queda_hecha(self):
        enqueue(tarea_simple, 9, nota='x')
        procesadas = ejecucion.procesar_pendientes(ahora=self.t0)
        self.assertEqual(procesadas, 1)
        self.assertEqual(LLAMADAS, [(9, 'x')])
        tarea = TareaPendiente.objects.get()
        self.assertEqual(tarea.estado, EstadoTarea.HECHA)
        self.assertEqual(tarea.intentos, 1)
        self.assertIsNotNone(tarea.terminada)

    def test_dos_corridas_seguidas_no_la_ejecutan_dos_veces(self):
        enqueue(tarea_simple, 1)
        ejecucion.procesar_pendientes(ahora=self.t0)
        ejecucion.procesar_pendientes(ahora=self.t0 + timedelta(hours=1))
        self.assertEqual(LLAMADAS, [(1, '')])

    def test_una_tarea_tomada_no_se_entrega_a_otro_trabajador(self):
        enqueue(tarea_simple, 1)
        primera = ejecucion.reclamar_siguiente(self.t0)
        segunda = ejecucion.reclamar_siguiente(self.t0)
        self.assertIsNotNone(primera)
        self.assertIsNone(segunda)
        self.assertEqual(primera.estado, EstadoTarea.EN_CURSO)

    def test_no_se_ejecuta_antes_de_su_proximo_intento(self):
        enqueue(tarea_simple, 1)
        TareaPendiente.objects.update(proximo_intento=self.t0 + timedelta(minutes=10))
        self.assertEqual(ejecucion.procesar_pendientes(ahora=self.t0), 0)
        self.assertEqual(ejecucion.procesar_pendientes(ahora=self.t0 + timedelta(minutes=10)), 1)

    def test_el_limite_acota_las_tareas_por_ciclo(self):
        for numero in range(5):
            enqueue(tarea_simple, numero)
        self.assertEqual(ejecucion.procesar_pendientes(ahora=self.t0, limite=2), 2)
        self.assertEqual(ejecucion.procesar_pendientes(ahora=self.t0), 3)

    def test_se_puede_pedir_parar_entre_tareas(self):
        for numero in range(3):
            enqueue(tarea_simple, numero)
        self.assertEqual(ejecucion.procesar_pendientes(ahora=self.t0, debe_parar=lambda: True), 0)
        self.assertEqual(TareaPendiente.objects.filter(estado=EstadoTarea.PENDIENTE).count(), 3)


@override_settings(TASK_BACKEND=BACKEND_BD)
class ReintentosTests(_Base):
    def test_la_espera_crece_con_cada_fallo(self):
        enqueue(tarea_que_falla)
        ahora = self.t0
        esperas = []
        for _ in range(4):
            with self.assertLogs('tareas.ejecucion', level='WARNING'):
                ejecucion.procesar_pendientes(ahora=ahora)
            tarea = TareaPendiente.objects.get()
            self.assertEqual(tarea.estado, EstadoTarea.PENDIENTE)
            esperas.append(int((tarea.proximo_intento - ahora).total_seconds()))
            ahora = tarea.proximo_intento
        self.assertEqual(esperas, [60, 300, 1800, 7200])

    def test_no_se_reintenta_antes_de_la_espera(self):
        enqueue(tarea_que_falla)
        with self.assertLogs('tareas.ejecucion', level='WARNING'):
            ejecucion.procesar_pendientes(ahora=self.t0)
        ejecucion.procesar_pendientes(ahora=self.t0 + timedelta(seconds=59))
        self.assertEqual(LLAMADAS, ['intento'])
        with self.assertLogs('tareas.ejecucion', level='WARNING'):
            ejecucion.procesar_pendientes(ahora=self.t0 + timedelta(seconds=60))
        self.assertEqual(LLAMADAS, ['intento', 'intento'])

    def test_un_reintento_exitoso_deja_la_tarea_hecha(self):
        ESTADO['falla'] = True
        enqueue(tarea_inestable)
        with self.assertLogs('tareas.ejecucion', level='WARNING'):
            ejecucion.procesar_pendientes(ahora=self.t0)
        ESTADO['falla'] = False
        ejecucion.procesar_pendientes(ahora=self.t0 + timedelta(minutes=1))
        tarea = TareaPendiente.objects.get()
        self.assertEqual(tarea.estado, EstadoTarea.HECHA)
        self.assertEqual(tarea.intentos, 2)
        self.assertEqual(tarea.ultimo_error, '')

    @override_settings(TAREAS_MAX_INTENTOS=3)
    def test_al_agotar_los_intentos_queda_fallida_y_se_reporta(self):
        enqueue(tarea_que_falla)
        ahora = self.t0
        for _ in range(2):
            with self.assertLogs('tareas.ejecucion', level='WARNING'):
                ejecucion.procesar_pendientes(ahora=ahora)
            ahora = TareaPendiente.objects.get().proximo_intento
        with self.assertLogs('tareas.ejecucion', level='ERROR') as registro:
            ejecucion.procesar_pendientes(ahora=ahora)
        tarea = TareaPendiente.objects.get()
        self.assertEqual(tarea.estado, EstadoTarea.FALLIDA)
        self.assertEqual(tarea.intentos, 3)
        self.assertIsNotNone(tarea.terminada)
        self.assertIsNotNone(registro.records[0].exc_info)
        # Una fallida no se vuelve a tomar.
        ejecucion.procesar_pendientes(ahora=ahora + timedelta(days=1))
        self.assertEqual(len(LLAMADAS), 3)

    def test_el_error_guardado_no_lleva_datos_personales(self):
        enqueue(tarea_que_falla)
        with self.assertLogs('tareas.ejecucion', level='WARNING'):
            ejecucion.procesar_pendientes(ahora=self.t0)
        error = TareaPendiente.objects.get().ultimo_error
        self.assertIn('RuntimeError', error)
        self.assertNotIn('persona@example.com', error)
        self.assertNotIn('1234567890', error)

    def test_el_error_se_recorta(self):
        self.assertLessEqual(len(ejecucion.resumir_error(ValueError('x' * 5000))), 300)

    def test_una_tarea_cuya_funcion_no_existe_falla_sin_romper_al_trabajador(self):
        TareaPendiente.objects.create(ruta='tareas.test_cola.no_existe')
        with self.assertLogs('tareas.ejecucion', level='WARNING'):
            ejecucion.procesar_pendientes(ahora=self.t0)
        self.assertEqual(TareaPendiente.objects.get().estado, EstadoTarea.PENDIENTE)

    @override_settings(TAREAS_TIEMPO_MAXIMO_SEGUNDOS=600)
    def test_una_tarea_en_curso_perdida_se_recupera(self):
        enqueue(tarea_simple, 1)
        ejecucion.reclamar_siguiente(self.t0)  # el trabajador muere aqui
        self.assertIsNone(ejecucion.reclamar_siguiente(self.t0 + timedelta(seconds=599)))
        recuperada = ejecucion.reclamar_siguiente(self.t0 + timedelta(seconds=601))
        self.assertIsNotNone(recuperada)
        self.assertEqual(recuperada.intentos, 2)

    @override_settings(TAREAS_TIEMPO_MAXIMO_SEGUNDOS=600, TAREAS_MAX_INTENTOS=1)
    def test_una_tarea_perdida_sin_intentos_queda_fallida(self):
        enqueue(tarea_simple, 1)
        ejecucion.reclamar_siguiente(self.t0)
        with self.assertLogs('tareas.ejecucion', level='ERROR'):
            self.assertIsNone(ejecucion.reclamar_siguiente(self.t0 + timedelta(seconds=700)))
        self.assertEqual(TareaPendiente.objects.get().estado, EstadoTarea.FALLIDA)

    def test_reintentar_devuelve_una_fallida_a_la_cola(self):
        tarea = TareaPendiente.objects.create(
            ruta='tareas.test_cola.tarea_simple', argumentos={'args': [1], 'kwargs': {}},
            estado=EstadoTarea.FALLIDA, intentos=5, ultimo_error='x', terminada=self.t0,
        )
        self.assertTrue(ejecucion.reintentar(tarea.pk, ahora=self.t0))
        tarea.refresh_from_db()
        self.assertEqual(
            (tarea.estado, tarea.intentos, tarea.ultimo_error, tarea.terminada),
            (EstadoTarea.PENDIENTE, 0, '', None),
        )

    def test_reintentar_ignora_las_que_no_estan_fallidas(self):
        tarea = TareaPendiente.objects.create(ruta='tareas.test_cola.tarea_simple', estado=EstadoTarea.HECHA)
        self.assertFalse(ejecucion.reintentar(tarea.pk))
        tarea.refresh_from_db()
        self.assertEqual(tarea.estado, EstadoTarea.HECHA)


@override_settings(TASK_BACKEND=BACKEND_BD)
class IdempotenciaTests(_Base):
    @override_settings(TAREAS_TIEMPO_MAXIMO_SEGUNDOS=600)
    def test_si_el_trabajador_muere_tras_el_efecto_el_reintento_no_lo_repite(self):
        from tareas.idempotencia import tarea_en_curso

        enqueue(tarea_con_efecto, 4)
        tarea = ejecucion.reclamar_siguiente(self.t0)
        with tarea_en_curso(tarea):
            tarea_con_efecto(4)  # el efecto ocurre y el trabajador muere antes de registrar el resultado
        self.assertEqual(LLAMADAS, [('efecto', 4)])
        ejecucion.procesar_pendientes(ahora=self.t0 + timedelta(seconds=700))
        self.assertEqual(LLAMADAS, [('efecto', 4)])
        self.assertEqual(TareaPendiente.objects.get().estado, EstadoTarea.HECHA)

    def test_si_la_funcion_falla_no_se_marca_y_el_reintento_la_ejecuta(self):
        ESTADO['despues_del_efecto'] = True
        enqueue(tarea_con_efecto, 4)
        with self.assertLogs('tareas.ejecucion', level='WARNING'):
            ejecucion.procesar_pendientes(ahora=self.t0)
        self.assertEqual(EfectoAplicado.objects.count(), 0)
        ESTADO['despues_del_efecto'] = False
        ejecucion.procesar_pendientes(ahora=self.t0 + timedelta(minutes=1))
        self.assertEqual(LLAMADAS, [('efecto', 4), ('efecto', 4)])
        self.assertEqual(EfectoAplicado.objects.count(), 1)

    def test_con_la_marca_puesta_el_reintento_no_repite_el_efecto(self):
        enqueue(tarea_con_efecto, 4)
        tarea = TareaPendiente.objects.get()
        EfectoAplicado.objects.create(tarea=tarea, nombre='tareas.test_cola.tarea_con_efecto')
        ejecucion.procesar_pendientes(ahora=self.t0)
        self.assertEqual(LLAMADAS, [])
        self.assertEqual(TareaPendiente.objects.get().estado, EstadoTarea.HECHA)

    def test_la_marca_se_escribe_al_terminar_bien(self):
        enqueue(tarea_con_efecto, 4)
        ejecucion.procesar_pendientes(ahora=self.t0)
        self.assertEqual(EfectoAplicado.objects.count(), 1)

    def test_un_hecho_nuevo_con_los_mismos_argumentos_si_se_ejecuta(self):
        enqueue(tarea_con_efecto, 4)
        enqueue(tarea_con_efecto, 4)
        ejecucion.procesar_pendientes(ahora=self.t0)
        self.assertEqual(LLAMADAS, [('efecto', 4), ('efecto', 4)])

    def test_reintentar_desde_el_panel_conserva_las_marcas(self):
        enqueue(tarea_con_efecto, 4)
        ejecucion.procesar_pendientes(ahora=self.t0)
        tarea = TareaPendiente.objects.get()
        TareaPendiente.objects.update(estado=EstadoTarea.FALLIDA)
        ejecucion.reintentar(tarea.pk, ahora=self.t0)
        ejecucion.procesar_pendientes(ahora=self.t0)
        self.assertEqual(LLAMADAS, [('efecto', 4)])
