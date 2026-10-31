"""El interruptor "Habilitar Coach" del panel y su efecto en la tienda.

`administracion` y `vendedor` no pueden importarse entre si; aqui se hablan
solo por URL y por el modelo resuelto por nombre."""
import json

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from . import exposicion
from .test_utilidades import aislar_catalogo, crear_producto


def _ajustes():
    return apps.get_model('administracion', 'PanelSettings').load()


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100)
class InterruptorDelCoachTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        aislar_catalogo()
        crear_producto('Leggins', [('M', 'gris', 3)])
        self.administrador = get_user_model().objects.create_user(
            email='admin-coach@example.com', username='admin-coach', password='x', is_staff=True,
        )

    def _tienda(self):
        return self.client.get('/es/').content.decode()

    def _mensaje(self):
        return self.client.post(
            '/es/vendedor/mensaje/', data=json.dumps({'message': 'hola'}),
            content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def _desde_el_panel(self, habilitar):
        administrador = self.client_class()
        administrador.force_login(self.administrador)
        return administrador.post(reverse('admin_coach_toggle'), {'habilitar': habilitar})

    def test_encendido_por_defecto_la_tienda_muestra_el_asistente(self):
        self.assertIn('data-vendedor-toggle', self._tienda())
        self.assertEqual(self._mensaje().status_code, 200)

    def test_el_administrador_lo_apaga_y_la_tienda_deja_de_mostrarlo(self):
        self._desde_el_panel('0')

        html = self._tienda()

        for rastro in ('data-vendedor', 'vendedor-panel', 'vendedor.js', 'vendedor.css'):
            self.assertNotIn(rastro, html)
        self.assertEqual(self._mensaje().status_code, 404)

    def test_el_administrador_lo_vuelve_a_encender(self):
        self._desde_el_panel('0')
        self._desde_el_panel('1')

        self.assertIn('data-vendedor-toggle', self._tienda())
        self.assertEqual(self._mensaje().status_code, 200)

    def test_apagarlo_no_cuenta_contra_el_limite_ni_llama_al_coach(self):
        self._desde_el_panel('0')

        self._mensaje()

        self.assertFalse(cache.get('vendedor:dia:ip:127.0.0.1'))

    @override_settings(COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False)
    def test_habilitado_pero_sin_servicio_configurado_no_se_muestra(self):
        self.assertTrue(_ajustes().coach_enabled)

        self.assertNotIn('data-vendedor', self._tienda())
        self.assertEqual(self._mensaje().status_code, 404)

    @override_settings(COACH_API_URL='https://coach.example/api/', VENDEDOR_COACH_SIMULADO=False)
    def test_habilitado_y_con_servicio_configurado_se_muestra(self):
        self.assertIn('data-vendedor-toggle', self._tienda())

    @override_settings(VENDEDOR_ENABLED=False)
    def test_el_corte_tecnico_gana_aunque_el_administrador_lo_habilite(self):
        self.assertTrue(_ajustes().coach_enabled)

        self.assertNotIn('data-vendedor', self._tienda())
        self.assertEqual(self._mensaje().status_code, 404)

    def test_las_politicas_siguen_al_asistente(self):
        con_asistente = self.client.get('/es/politica-tratamiento-datos/').content.decode()
        self._desde_el_panel('0')
        sin_asistente = self.client.get('/es/politica-tratamiento-datos/').content.decode()

        self.assertIn('Quantum Coach, la inteligencia artificial de GoToGym', con_asistente)
        self.assertNotIn('Quantum Coach, la inteligencia artificial de GoToGym', sin_asistente)


class AsistenteActivoTests(TestCase):
    @override_settings(VENDEDOR_ENABLED=True)
    def test_las_tres_condiciones(self):
        casos = [
            # (corte tecnico, hay servicio, administrador, esperado)
            (True, True, True, True),
            (False, True, True, False),
            (True, False, True, False),
            (True, True, False, False),
        ]
        for corte, servicio, administrador, esperado in casos:
            with self.subTest(corte=corte, servicio=servicio, administrador=administrador), \
                    override_settings(
                        VENDEDOR_ENABLED=corte, COACH_API_URL='https://c.example/' if servicio else '',
                        VENDEDOR_COACH_SIMULADO=False,
                    ):
                ajustes = _ajustes()
                ajustes.coach_enabled = administrador
                ajustes.save()
                self.assertEqual(exposicion.asistente_activo(), esperado)

    @override_settings(VENDEDOR_ENABLED=False)
    def test_con_el_corte_apagado_no_consulta_la_base(self):
        with self.assertNumQueries(0):
            exposicion.asistente_activo()

    @override_settings(VENDEDOR_ENABLED=True, COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False)
    def test_sin_servicio_no_consulta_la_base(self):
        with self.assertNumQueries(0):
            exposicion.asistente_activo()
