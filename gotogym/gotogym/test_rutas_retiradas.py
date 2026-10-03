"""Rutas heredadas que ya no existen: responden 404 y no redirigen a ninguna parte."""
from django.test import TestCase


class RutasRetiradasTests(TestCase):
    def test_las_rutas_heredadas_ya_no_existen(self):
        for ruta in (
            '/es/pedidos/', '/es/bienestar/', '/es/gestion/', '/es/tecnologia/',
            '/es/configuracion-marca/', '/es/metricas/', '/es/products/products/',
        ):
            self.assertEqual(self.client.get(ruta).status_code, 404, ruta)

    def test_la_ruta_de_la_antigua_portada_con_sesion_sigue_redirigiendo(self):
        respuesta = self.client.get('/es/welcome/')
        self.assertEqual((respuesta.status_code, respuesta['Location']), (301, '/es/'))
