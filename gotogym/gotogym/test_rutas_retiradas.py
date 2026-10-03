"""Rutas heredadas que ya no existen: responden 404, salvo compatibilidad de rutas antiguas reubicadas."""
from django.test import TestCase


class RutasRetiradasTests(TestCase):
    def test_las_rutas_heredadas_ya_no_existen(self):
        for ruta in (
            '/es/pedidos/', '/es/bienestar/', '/es/gestion/', '/es/tecnologia/',
            '/es/configuracion-marca/', '/es/metricas/',
        ):
            self.assertEqual(self.client.get(ruta).status_code, 404, ruta)

    def test_la_ruta_legacy_de_productos_redirige_a_tienda(self):
        for ruta in ('/products/products/', '/es/products/products/'):
            respuesta = self.client.get(ruta)
            self.assertEqual(respuesta.status_code, 302, ruta)
            self.assertEqual(respuesta['Location'], '/es/tienda/', ruta)

    def test_la_ruta_de_la_antigua_portada_con_sesion_sigue_redirigiendo(self):
        respuesta = self.client.get('/es/welcome/')
        self.assertEqual((respuesta.status_code, respuesta['Location']), (301, '/es/'))
