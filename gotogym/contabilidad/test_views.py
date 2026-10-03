"""Panel de contabilidad (Alegra): acceso restringido a staff y comportamiento
ante datos y ante fallos de la API, siempre con el cliente simulado."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contabilidad.views import MENSAJE_ERROR, MENSAJE_SIN_CREDENCIALES

CLIENTES = [
    {'id': 1, 'name': 'Ana Marin', 'email': 'ana@example.com'},
    {'id': 2, 'name': 'Luis Soto', 'email': 'luis@example.com'},
]
FACTURAS = [
    {'number': 'F-100', 'status': 'open', 'client': {'id': '1'}},
    {'number': 'F-200', 'status': 'closed', 'client': {'id': '1'}},
    {'number': 'F-300', 'status': 'open', 'client': {'id': '2'}},
]


@patch('contabilidad.views.AlegraClient')
class ContabilidadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            email='conta-staff@example.com', username='conta-staff@example.com',
            password='secret123', is_staff=True,
        )
        cls.cliente_comun = User.objects.create_user(
            email='conta-user@example.com', username='conta-user@example.com', password='secret123',
        )

    def _api(self, alegra, *, clientes=CLIENTES, facturas=FACTURAS):
        api = alegra.return_value
        api.get_clients.return_value = clientes
        api.get_invoices.return_value = facturas
        return api

    def test_anonimo_y_usuario_comun_no_entran(self, alegra):
        url = reverse('contabilidad:clientes')
        anonimo = self.client.get(url)
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn(reverse('commercial_login'), anonimo.url)

        self.client.force_login(self.cliente_comun)
        self.assertEqual(self.client.get(url).status_code, 302)
        alegra.assert_not_called()

    def test_staff_ve_los_clientes(self, alegra):
        self._api(alegra)
        self.client.force_login(self.staff)
        respuesta = self.client.get(reverse('contabilidad:clientes'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['clientes'], CLIENTES)
        self.assertIsNone(respuesta.context['error'])

    def test_filtra_por_nombre_o_correo_sin_importar_mayusculas(self, alegra):
        self._api(alegra)
        self.client.force_login(self.staff)
        por_nombre = self.client.get(reverse('contabilidad:clientes'), {'filtro': 'ANA'})
        self.assertEqual([c['id'] for c in por_nombre.context['clientes']], [1])
        por_correo = self.client.get(reverse('contabilidad:clientes'), {'filtro': 'luis@'})
        self.assertEqual([c['id'] for c in por_correo.context['clientes']], [2])

    def test_si_la_api_falla_muestra_el_error_y_no_rompe(self, alegra):
        alegra.side_effect = ValueError('Alegra credentials are required')
        self.client.force_login(self.staff)
        respuesta = self.client.get(reverse('contabilidad:clientes'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['clientes'], [])
        self.assertEqual(respuesta.context['error'], MENSAJE_SIN_CREDENCIALES)

    def test_facturas_de_un_cliente(self, alegra):
        self._api(alegra)
        self.client.force_login(self.staff)
        respuesta = self.client.get(reverse('contabilidad:facturas_cliente', args=[1]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['cliente']['name'], 'Ana Marin')
        self.assertEqual([f['number'] for f in respuesta.context['facturas']], ['F-100', 'F-200'])

    def test_filtra_facturas_por_numero_o_estado(self, alegra):
        self._api(alegra)
        self.client.force_login(self.staff)
        url = reverse('contabilidad:facturas_cliente', args=[1])
        por_estado = self.client.get(url, {'filtro_factura': 'closed'})
        self.assertEqual([f['number'] for f in por_estado.context['facturas']], ['F-200'])
        por_numero = self.client.get(url, {'filtro_factura': 'f-100'})
        self.assertEqual([f['number'] for f in por_numero.context['facturas']], ['F-100'])

    def test_cliente_inexistente_no_rompe(self, alegra):
        self._api(alegra)
        self.client.force_login(self.staff)
        respuesta = self.client.get(reverse('contabilidad:facturas_cliente', args=[99]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context['cliente'])
        self.assertEqual(respuesta.context['facturas'], [])

    def test_facturas_con_la_api_caida(self, alegra):
        alegra.return_value.get_clients.side_effect = RuntimeError('500 https://api.alegra.com/token=abc')
        self.client.force_login(self.staff)
        with self.assertLogs('contabilidad.views', level='ERROR'):
            respuesta = self.client.get(reverse('contabilidad:facturas_cliente', args=[1]))
        self.assertEqual(respuesta.status_code, 200)
        # Se muestra un mensaje generico: el detalle del fallo no sale a pantalla.
        self.assertEqual(respuesta.context['error'], MENSAJE_ERROR)
        self.assertNotContains(respuesta, 'api.alegra.com')
        self.assertNotContains(respuesta, 'token=abc')
