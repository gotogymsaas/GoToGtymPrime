"""Interruptor "Habilitar Coach" de la barra superior del panel: reemplaza al de
pausa de compras y decide si la tienda muestra el asistente de compras con IA."""
import importlib

from django.apps import apps as aplicaciones
from django.test import override_settings
from django.urls import reverse

from administracion.models import PanelSettings
from administracion.test_admin_panel import PanelAdminBaseTestCase


class InterruptorDelCoachTests(PanelAdminBaseTestCase):
    def _alternar(self, valor='0'):
        return self.client.post(reverse('admin_coach_toggle'), {'habilitar': valor})

    def test_por_defecto_el_coach_esta_habilitado(self):
        self.assertTrue(PanelSettings.coach_habilitado())
        self.assertTrue(PanelSettings.load().coach_enabled)

    def test_deshabilitar_y_habilitar(self):
        self._alternar('0')
        self.assertFalse(PanelSettings.coach_habilitado())
        self._alternar('1')
        self.assertTrue(PanelSettings.coach_habilitado())

    def test_repetir_la_misma_accion_no_cambia_nada(self):
        self._alternar('0')
        self._alternar('0')
        self.assertFalse(PanelSettings.coach_habilitado())

    def test_el_panel_muestra_el_interruptor_con_su_confirmacion(self):
        respuesta = self.client.get(reverse('admin_dashboard'))

        self.assertContains(respuesta, 'Habilitar Coach')
        self.assertContains(respuesta, '¿Deshabilitar el Coach?')
        self.assertContains(respuesta, 'data-coach-open')
        self.assertContains(respuesta, 'aria-checked="true"')
        self.assertNotContains(respuesta, 'Quantum Coach está deshabilitado')

    def test_deshabilitado_el_panel_lo_dice_y_ofrece_volver_a_habilitarlo(self):
        self._alternar('0')

        respuesta = self.client.get(reverse('admin_dashboard'))

        self.assertContains(respuesta, 'Quantum Coach está deshabilitado')
        self.assertContains(respuesta, '¿Habilitar el Coach?')
        self.assertContains(respuesta, 'pause-switch is-paused')

    def test_el_interruptor_de_compras_ya_no_esta_en_el_panel(self):
        respuesta = self.client.get(reverse('admin_dashboard'))

        for texto in ('Compras activas', 'Compras en pausa', '¿Pausar las compras?', 'data-pause-open'):
            with self.subTest(texto=texto):
                self.assertNotContains(respuesta, texto)

    def test_el_endpoint_de_pausa_de_compras_ya_no_existe(self):
        respuesta = self.client.post('/es/admin-panel/pausa-compras/', {'pausar': '1'})

        self.assertEqual(respuesta.status_code, 404)

    def test_un_cliente_no_puede_cambiarlo(self):
        self.client.force_login(self.cliente)

        self._alternar('0')

        self.assertTrue(PanelSettings.coach_habilitado())

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get(reverse('admin_coach_toggle')).status_code, 405)

    @override_settings(COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False)
    def test_habilitar_sin_servicio_configurado_lo_avisa(self):
        self._alternar('0')

        respuesta = self.client.post(reverse('admin_coach_toggle'), {'habilitar': '1'}, follow=True)

        self.assertContains(respuesta, 'no tiene el servicio de IA configurado')

    @override_settings(COACH_API_URL='https://coach.example/api/', VENDEDOR_COACH_SIMULADO=False)
    def test_habilitar_con_servicio_configurado_confirma(self):
        self._alternar('0')

        respuesta = self.client.post(reverse('admin_coach_toggle'), {'habilitar': '1'}, follow=True)

        self.assertContains(respuesta, 'Coach habilitado: Quantum Coach se muestra en la tienda.')

    def test_deshabilitar_confirma_que_ya_no_se_muestra(self):
        respuesta = self.client.post(reverse('admin_coach_toggle'), {'habilitar': '0'}, follow=True)

        self.assertContains(respuesta, 'Coach deshabilitado')

    def test_no_toca_el_estado_de_las_compras_ni_de_los_pagos(self):
        self._alternar('0')

        ajustes = PanelSettings.load()

        self.assertFalse(ajustes.purchases_paused)
        self.assertTrue(ajustes.online_payments_enabled)


class MigracionReanudaComprasTests(PanelAdminBaseTestCase):
    """El interruptor de pausa sale del panel: una base que lo tuviera en
    pausa no podria reanudar las compras, asi que la migracion la reanuda."""

    def test_una_base_en_pausa_queda_vendiendo(self):
        migracion = importlib.import_module('administracion.migrations.0007_panelsettings_coach_enabled')
        ajustes = PanelSettings.load()
        ajustes.purchases_paused = True
        ajustes.save()

        migracion.reanudar_compras(aplicaciones, None)

        ajustes.refresh_from_db()
        self.assertFalse(ajustes.purchases_paused)
        self.assertIsNone(ajustes.purchases_paused_at)

    def test_no_toca_las_demas_opciones(self):
        migracion = importlib.import_module('administracion.migrations.0007_panelsettings_coach_enabled')
        ajustes = PanelSettings.load()
        ajustes.online_payments_enabled = False
        ajustes.coach_enabled = False
        ajustes.save()

        migracion.reanudar_compras(aplicaciones, None)

        ajustes.refresh_from_db()
        self.assertFalse(ajustes.online_payments_enabled)
        self.assertFalse(ajustes.coach_enabled)
