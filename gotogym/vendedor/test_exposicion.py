"""Quien ve el vendedor: interruptor general y porcentaje de exposicion."""
import hashlib

from analitica.services import hash_visitante
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import exposicion


def _peticion(sesion=None):
    request = RequestFactory().get('/es/')
    request.user = AnonymousUser()
    request.session = {} if sesion is None else sesion
    return request


def _hashes(cantidad):
    return [hashlib.sha256(f'visitante-{n}'.encode()).hexdigest()[:32] for n in range(cantidad)]


class GrupoTests(SimpleTestCase):
    def test_el_grupo_es_estable_para_el_mismo_visitante(self):
        for visitante in _hashes(20):
            self.assertEqual(
                exposicion.grupo_del_visitante(visitante, 50),
                exposicion.grupo_del_visitante(visitante, 50),
            )

    def test_los_extremos(self):
        self.assertEqual({exposicion.grupo_del_visitante(h, 100) for h in _hashes(200)}, {'vendedor'})
        self.assertEqual({exposicion.grupo_del_visitante(h, 0) for h in _hashes(200)}, {'control'})

    def test_el_reparto_se_acerca_al_porcentaje(self):
        for porcentaje in (10, 30, 50, 80):
            with self.subTest(porcentaje=porcentaje):
                visitantes = _hashes(4000)
                expuestos = sum(exposicion.grupo_del_visitante(h, porcentaje) == 'vendedor' for h in visitantes)
                self.assertAlmostEqual(expuestos / len(visitantes) * 100, porcentaje, delta=3)

    def test_subir_el_porcentaje_no_saca_a_quien_ya_lo_veia(self):
        visitantes = _hashes(500)
        con_30 = {h for h in visitantes if exposicion.grupo_del_visitante(h, 30) == 'vendedor'}
        con_60 = {h for h in visitantes if exposicion.grupo_del_visitante(h, 60) == 'vendedor'}

        self.assertTrue(con_30 <= con_60)

    @override_settings(VENDEDOR_ROLLOUT_PERCENT=25)
    def test_sin_porcentaje_explicito_usa_la_configuracion(self):
        visitantes = _hashes(2000)
        expuestos = sum(exposicion.grupo_del_visitante(h) == 'vendedor' for h in visitantes)

        self.assertAlmostEqual(expuestos / len(visitantes) * 100, 25, delta=3)


class VisibleParaTests(TestCase):
    @override_settings(VENDEDOR_ENABLED=False, VENDEDOR_ROLLOUT_PERCENT=100)
    def test_apagado_no_lo_ve_nadie(self):
        self.assertFalse(exposicion.visible_para(_peticion()))

    @override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100)
    def test_al_cien_por_ciento_no_hace_falta_identificar_al_visitante(self):
        peticion = _peticion()

        self.assertTrue(exposicion.visible_para(peticion))
        self.assertEqual(peticion.session, {})  # no se creo identificador

    @override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=0)
    def test_al_cero_por_ciento_no_lo_ve_nadie_y_tampoco_se_identifica(self):
        peticion = _peticion()

        self.assertFalse(exposicion.visible_para(peticion))
        self.assertEqual(peticion.session, {})

    @override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=50)
    def test_con_porcentaje_parcial_decide_el_hash_del_visitante(self):
        peticion = _peticion()

        visible = exposicion.visible_para(peticion)

        esperado = exposicion.grupo_del_visitante(hash_visitante(peticion), 50) == 'vendedor'
        self.assertEqual(visible, esperado)

    @override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=50)
    def test_la_misma_sesion_ve_siempre_lo_mismo(self):
        sesion = {}
        resultados = {exposicion.visible_para(_peticion(sesion)) for _ in range(10)}

        self.assertEqual(len(resultados), 1)


class ContextoDePlantillaTests(TestCase):
    @override_settings(VENDEDOR_ENABLED=False)
    def test_apagado_las_plantillas_no_lo_muestran(self):
        respuesta = self.client.get(reverse('home'))

        self.assertFalse(respuesta.context['vendedor_visible'])

    @override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100)
    def test_encendido_las_plantillas_lo_muestran(self):
        respuesta = self.client.get(reverse('home'))

        self.assertTrue(respuesta.context['vendedor_visible'])
        self.assertTrue(respuesta.context['vendedor_disponible'])

    @override_settings(VENDEDOR_ENABLED=True, COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False)
    def test_sin_servicio_se_muestra_pero_no_esta_disponible(self):
        respuesta = self.client.get(reverse('home'))

        self.assertTrue(respuesta.context['vendedor_visible'])
        self.assertFalse(respuesta.context['vendedor_disponible'])

    @override_settings(VENDEDOR_ENABLED=False, COACH_API_URL='https://c.example/')
    def test_apagado_no_esta_ni_visible_ni_disponible(self):
        respuesta = self.client.get(reverse('home'))

        self.assertFalse(respuesta.context['vendedor_visible'])
        self.assertFalse(respuesta.context['vendedor_disponible'])
