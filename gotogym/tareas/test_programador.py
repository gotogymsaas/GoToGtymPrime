"""Tareas periodicas: se encolan cuando toca y no antes; la purga."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.module_loading import import_string

from tareas import ejecucion, periodicas, programador
from tareas.models import EfectoAplicado, EstadoTarea, TareaPendiente, TareaPeriodica

LLAMADAS: list = []


def periodica_de_prueba():
    LLAMADAS.append('corrio')


class CatalogoTests(TestCase):
    def test_las_rutas_del_catalogo_existen(self):
        for nombre, ruta, intervalo in programador.CATALOGO:
            self.assertTrue(callable(import_string(ruta)), nombre)
            self.assertGreater(intervalo, 0)

    def test_el_catalogo_inicial_trae_las_tareas_acordadas(self):
        intervalos = {nombre: intervalo for nombre, _, intervalo in programador.CATALOGO}
        self.assertEqual(intervalos['cancelar_pedidos_vencidos'], 3600)
        self.assertEqual(intervalos['emitir_facturas_pendientes'], 900)
        self.assertEqual(intervalos['confirmar_comisiones'], 86400)
        self.assertEqual(intervalos['aplicar_bajas_de_afiliados'], 86400)
        self.assertEqual(intervalos['purgar_analitica'], 86400)
        self.assertEqual(intervalos['limpiar_sesiones'], 86400)
        self.assertEqual(intervalos['purgar_tareas_terminadas'], 86400)

    def test_sincronizar_crea_las_filas_y_es_repetible(self):
        programador.sincronizar_catalogo()
        programador.sincronizar_catalogo()
        self.assertEqual(TareaPeriodica.objects.count(), len(programador.CATALOGO))

    def test_sincronizar_respeta_una_tarea_apagada_a_mano(self):
        programador.sincronizar_catalogo()
        TareaPeriodica.objects.filter(nombre='purgar_analitica').update(activa=False)
        programador.sincronizar_catalogo()
        self.assertFalse(TareaPeriodica.objects.get(nombre='purgar_analitica').activa)

    def test_sincronizar_actualiza_intervalo_y_desactiva_las_retiradas(self):
        TareaPeriodica.objects.create(nombre='purgar_analitica', ruta='x.y', intervalo_segundos=5)
        TareaPeriodica.objects.create(nombre='ya_no_existe', ruta='x.y', intervalo_segundos=5)
        programador.sincronizar_catalogo()
        self.assertEqual(TareaPeriodica.objects.get(nombre='purgar_analitica').intervalo_segundos, 86400)
        self.assertFalse(TareaPeriodica.objects.get(nombre='ya_no_existe').activa)


class EncolarPeriodicasTests(TestCase):
    def setUp(self):
        LLAMADAS.clear()
        self.t0 = timezone.now()
        TareaPeriodica.objects.create(
            nombre='prueba', ruta='tareas.test_programador.periodica_de_prueba', intervalo_segundos=3600,
        )

    def test_la_primera_vez_se_encola(self):
        self.assertEqual(programador.encolar_periodicas(self.t0), ['prueba'])
        tarea = TareaPendiente.objects.get()
        self.assertEqual(tarea.ruta, 'tareas.test_programador.periodica_de_prueba')
        self.assertTrue(tarea.clave_idempotencia.startswith('periodica:prueba:'))
        self.assertEqual(TareaPeriodica.objects.get().ultima_ejecucion, self.t0)

    def test_no_se_encola_antes_de_que_toque(self):
        programador.encolar_periodicas(self.t0)
        TareaPendiente.objects.update(estado=EstadoTarea.HECHA)
        self.assertEqual(programador.encolar_periodicas(self.t0 + timedelta(minutes=59)), [])
        self.assertEqual(TareaPendiente.objects.count(), 1)

    def test_se_encola_de_nuevo_cuando_toca(self):
        programador.encolar_periodicas(self.t0)
        TareaPendiente.objects.update(estado=EstadoTarea.HECHA)
        self.assertEqual(programador.encolar_periodicas(self.t0 + timedelta(hours=1)), ['prueba'])
        self.assertEqual(TareaPendiente.objects.count(), 2)

    def test_dos_trabajadores_no_la_encolan_dos_veces(self):
        # Otro trabajador gana la reclamacion entre la lectura y la actualizacion.
        def le_toca_y_otro_la_gana(periodica, ahora):
            TareaPeriodica.objects.filter(pk=periodica.pk).update(ultima_ejecucion=self.t0)
            return True

        with patch.object(programador, '_le_toca', le_toca_y_otro_la_gana):
            self.assertEqual(programador.encolar_periodicas(self.t0 + timedelta(hours=2)), [])
        self.assertEqual(TareaPendiente.objects.count(), 0)

    def test_si_la_anterior_sigue_en_cola_no_se_apila_otra(self):
        programador.encolar_periodicas(self.t0)
        self.assertEqual(programador.encolar_periodicas(self.t0 + timedelta(hours=3)), [])
        self.assertEqual(TareaPendiente.objects.count(), 1)

    def test_una_apagada_no_se_encola(self):
        TareaPeriodica.objects.update(activa=False)
        self.assertEqual(programador.encolar_periodicas(self.t0), [])

    def test_la_tarea_encolada_se_ejecuta(self):
        programador.encolar_periodicas(self.t0)
        ejecucion.procesar_pendientes(ahora=self.t0)
        self.assertEqual(LLAMADAS, ['corrio'])


class FuncionesPeriodicasTests(TestCase):
    def test_los_comandos_se_reutilizan_por_nombre(self):
        with patch('tareas.periodicas.call_command') as llamar:
            periodicas.emitir_facturas_pendientes()
            periodicas.purgar_analitica()
            periodicas.limpiar_sesiones()
        self.assertEqual([c.args[0] for c in llamar.call_args_list],
                         ['emitir_facturas_pendientes', 'purgar_analitica', 'clearsessions'])

    def test_los_comandos_reales_corren_sin_error(self):
        periodicas.emitir_facturas_pendientes()
        periodicas.purgar_analitica()
        periodicas.limpiar_sesiones()

    @override_settings(TAREAS_RETENCION_DIAS=30)
    def test_purga_las_terminadas_con_mas_de_treinta_dias(self):
        ahora = timezone.now()
        vieja = TareaPendiente.objects.create(
            ruta='a.b', estado=EstadoTarea.HECHA, terminada=ahora - timedelta(days=31))
        vieja_fallida = TareaPendiente.objects.create(
            ruta='a.b', estado=EstadoTarea.FALLIDA, terminada=ahora - timedelta(days=31))
        reciente = TareaPendiente.objects.create(
            ruta='a.b', estado=EstadoTarea.HECHA, terminada=ahora - timedelta(days=29))
        pendiente = TareaPendiente.objects.create(ruta='a.b', creada=ahora - timedelta(days=90))
        en_curso = TareaPendiente.objects.create(
            ruta='a.b', estado=EstadoTarea.EN_CURSO, creada=ahora - timedelta(days=90))
        EfectoAplicado.objects.create(tarea=vieja, nombre='x')

        self.assertEqual(periodicas.purgar_tareas_terminadas(ahora), 3)  # incluye la marca en cascada
        self.assertFalse(TareaPendiente.objects.filter(pk__in=[vieja.pk, vieja_fallida.pk]).exists())
        self.assertEqual(EfectoAplicado.objects.count(), 0)
        self.assertEqual(
            set(TareaPendiente.objects.values_list('pk', flat=True)), {reciente.pk, pendiente.pk, en_curso.pk})
