"""Los interruptores del panel se leen una sola vez por peticion."""
from django.apps import apps
from django.test import RequestFactory, TestCase

from . import ajustes_tienda


def _fijar(**campos):
    modelo = apps.get_model('administracion', 'PanelSettings')
    modelo.objects.update_or_create(pk=1, defaults=campos)


class AjustesPorPeticionTests(TestCase):
    def setUp(self):
        self.peticion = RequestFactory().get('/')

    def test_los_tres_interruptores_comparten_una_consulta(self):
        with self.assertNumQueries(1):
            ajustes_tienda.compras_pausadas(self.peticion)
            ajustes_tienda.pagos_habilitados(self.peticion)
            ajustes_tienda.coach_habilitado(self.peticion)

    def test_sin_peticion_cada_lectura_consulta_la_base(self):
        with self.assertNumQueries(2):
            ajustes_tienda.compras_pausadas()
            ajustes_tienda.pagos_habilitados()

    def test_sin_fila_valen_los_valores_por_defecto(self):
        self.assertFalse(ajustes_tienda.compras_pausadas(self.peticion))
        self.assertTrue(ajustes_tienda.pagos_habilitados(self.peticion))
        self.assertTrue(ajustes_tienda.coach_habilitado(self.peticion))

    def test_un_cambio_se_ve_en_la_siguiente_peticion(self):
        self.assertFalse(ajustes_tienda.compras_pausadas(RequestFactory().get('/')))

        _fijar(purchases_paused=True, coach_enabled=False)

        siguiente = RequestFactory().get('/')
        self.assertTrue(ajustes_tienda.compras_pausadas(siguiente))
        self.assertFalse(ajustes_tienda.coach_habilitado(siguiente))
        self.assertTrue(ajustes_tienda.pagos_habilitados(siguiente))

    def test_dentro_de_una_peticion_se_conserva_la_primera_lectura(self):
        self.assertFalse(ajustes_tienda.compras_pausadas(self.peticion))

        _fijar(purchases_paused=True)

        self.assertFalse(ajustes_tienda.compras_pausadas(self.peticion))
        self.assertTrue(ajustes_tienda.compras_pausadas())
