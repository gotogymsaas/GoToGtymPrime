"""Clientes de integraciones externas, siempre contra dobles: ninguna prueba
hace una llamada de red real."""
import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from integrations.alegra.alegra_client import AlegraClient
from integrations.hubspot.hubspot_client import HubSpotClient
from integrations.mercadopago import mercadopago_client
from integrations.mercadopago.mercadopago_client import MercadoPagoClient


class AlegraClientHttpTests(SimpleTestCase):
    def setUp(self):
        self.cliente = AlegraClient(email='user@example.com', token='token')

    def _respuesta(self, cuerpo):
        respuesta = MagicMock()
        respuesta.json.return_value = cuerpo
        return respuesta

    def test_exige_credenciales(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                AlegraClient()

    def test_la_autenticacion_es_basic_con_correo_y_token(self):
        # base64("user@example.com:token")
        self.assertEqual(
            self.cliente.headers['Authorization'], 'Basic dXNlckBleGFtcGxlLmNvbTp0b2tlbg==',
        )

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_lista_clientes(self, get):
        get.return_value = self._respuesta([{'id': 1, 'name': 'Ana'}])
        self.assertEqual(self.cliente.get_clients(), [{'id': 1, 'name': 'Ana'}])
        self.assertTrue(get.call_args.args[0].endswith('/contacts'))

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_lista_facturas(self, get):
        get.return_value = self._respuesta([{'number': 'F-1'}])
        self.assertEqual(self.cliente.get_invoices(), [{'number': 'F-1'}])
        self.assertTrue(get.call_args.args[0].endswith('/invoices'))

    @patch('integrations.alegra.alegra_client.requests.post')
    def test_crea_factura(self, post):
        post.return_value = self._respuesta({'id': 9})
        self.assertEqual(self.cliente.create_invoice({'client': 1}), {'id': 9})
        self.assertEqual(post.call_args.kwargs['json'], {'client': 1})
        self.assertTrue(post.call_args.args[0].endswith('/invoices'))

    @patch('integrations.alegra.alegra_client.requests.post')
    def test_registra_gasto(self, post):
        post.return_value = self._respuesta({'id': 3})
        self.assertEqual(self.cliente.record_expense({'amount': 10}), {'id': 3})
        self.assertTrue(post.call_args.args[0].endswith('/expenses'))

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_un_error_http_se_propaga(self, get):
        respuesta = self._respuesta([])
        respuesta.raise_for_status.side_effect = RuntimeError('401')
        get.return_value = respuesta
        with self.assertRaises(RuntimeError):
            self.cliente.get_clients()


class MercadoPagoClientTests(SimpleTestCase):
    def setUp(self):
        self.sdk = MagicMock()
        parche = patch.object(mercadopago_client, 'mercadopago', MagicMock(SDK=MagicMock(return_value=self.sdk)))
        parche.start()
        self.addCleanup(parche.stop)

    def test_crea_preferencia_y_devuelve_la_respuesta(self):
        self.sdk.preference.return_value.create.return_value = {'response': {'id': 'pref-1'}}
        cliente = MercadoPagoClient(access_token='tok')
        self.assertEqual(cliente.create_preference({'items': []}), {'id': 'pref-1'})
        self.sdk.preference.return_value.create.assert_called_once_with({'items': []})

    def test_respuesta_sin_cuerpo_devuelve_vacio(self):
        self.sdk.preference.return_value.create.return_value = {}
        self.assertEqual(MercadoPagoClient(access_token='tok').create_preference({}), {})

    def test_reembolso_total_no_envia_monto(self):
        self.sdk.refund.return_value.create.return_value = {'response': {'id': 7}}
        self.assertEqual(MercadoPagoClient(access_token='tok').refund_payment('pay-1'), {'id': 7})
        self.sdk.refund.return_value.create.assert_called_once_with('pay-1', None)

    def test_reembolso_parcial_envia_el_monto(self):
        self.sdk.refund.return_value.create.return_value = {'response': {}}
        MercadoPagoClient(access_token='tok').refund_payment('pay-1', amount=25.5)
        self.sdk.refund.return_value.create.assert_called_once_with('pay-1', {'amount': 25.5})

    def test_toma_el_token_del_entorno(self):
        with patch.dict(os.environ, {'MERCADOPAGO_ACCESS_TOKEN': 'del-entorno'}):
            self.assertEqual(MercadoPagoClient().access_token, 'del-entorno')


class MercadoPagoSinPaqueteTests(SimpleTestCase):
    def test_sin_la_libreria_falla_con_un_mensaje_claro(self):
        with patch.object(mercadopago_client, 'mercadopago', None):
            with self.assertRaises(RuntimeError):
                MercadoPagoClient(access_token='tok')


class HubSpotClientTests(SimpleTestCase):
    def test_usa_el_token_recibido_o_el_del_entorno(self):
        self.assertEqual(HubSpotClient(token='abc').token, 'abc')
        with patch.dict(os.environ, {'HUBSPOT_PRIVATE_TOKEN': 'env'}):
            self.assertEqual(HubSpotClient().token, 'env')

    def test_crear_contacto_es_un_esqueleto_que_no_falla(self):
        self.assertIsNone(HubSpotClient(token='abc').create_contact('a@b.co', {'x': 1}))
