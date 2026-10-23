"""Clientes de integraciones externas, siempre contra dobles: ninguna prueba
hace una llamada de red real."""
import os
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase

from integrations.alegra import alegra_client
from integrations.alegra.alegra_client import AlegraClient, AlegraError
from integrations.mercadopago import mercadopago_client
from integrations.mercadopago.mercadopago_client import MercadoPagoClient, MercadoPagoError


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
    def test_un_error_inesperado_se_propaga(self, get):
        respuesta = self._respuesta([])
        respuesta.raise_for_status.side_effect = RuntimeError('401')
        get.return_value = respuesta
        with self.assertRaises(RuntimeError):
            self.cliente.get_clients()

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_cada_llamada_lleva_timeout(self, get):
        get.return_value = self._respuesta([])
        self.cliente.get_clients()
        self.assertEqual(get.call_args.kwargs['timeout'], alegra_client.TIMEOUT)

    @patch('integrations.alegra.alegra_client.requests.post')
    def test_un_error_http_de_alegra_se_convierte_en_alegra_error(self, post):
        error_http = requests.HTTPError('400 Client Error: https://api.alegra.com/secreto')
        error_http.response = MagicMock(status_code=400)
        error_http.response.json.return_value = {'error': 'falta la numeración', 'invoice': {'id': 5}}
        respuesta = self._respuesta({})
        respuesta.raise_for_status.side_effect = error_http
        post.return_value = respuesta

        with self.assertRaises(AlegraError) as contexto:
            self.cliente.create_invoice({})

        self.assertEqual(contexto.exception.status, 400)
        self.assertEqual(contexto.exception.payload['invoice']['id'], 5)
        self.assertIn('falta la numeración', str(contexto.exception))
        self.assertNotIn('alegra.com', str(contexto.exception))

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_un_fallo_de_red_se_convierte_en_alegra_error(self, get):
        get.side_effect = requests.ConnectionError('https://api.alegra.com/x')
        with self.assertRaises(AlegraError) as contexto:
            self.cliente.get_clients()
        self.assertIsNone(contexto.exception.status)
        self.assertNotIn('alegra.com', str(contexto.exception))

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_busca_un_contacto_por_documento_exacto(self, get):
        get.return_value = self._respuesta([
            {'id': 1, 'identification': '1020304050123'},
            {'id': 2, 'identificationObject': {'type': 'CC', 'number': '1020304050'}},
        ])
        self.assertEqual(self.cliente.find_contact('1.020.304.050')['id'], 2)
        self.assertEqual(get.call_args.kwargs['params']['identification'], '1020304050')

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_busca_un_nit_con_su_digito_de_verificacion(self, get):
        get.return_value = self._respuesta([{'id': 3, 'identification': '900123456-8'}])
        self.assertEqual(self.cliente.find_contact('900123456', dv='8')['id'], 3)

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_contacto_inexistente_devuelve_none(self, get):
        get.return_value = self._respuesta([{'id': 1, 'identification': '999'}])
        self.assertIsNone(self.cliente.find_contact('1020304050'))

    @patch('integrations.alegra.alegra_client.requests.get')
    def test_busca_un_producto_por_referencia_exacta(self, get):
        get.return_value = self._respuesta([
            {'id': 1, 'reference': 'SKU-10'}, {'id': 2, 'reference': 'SKU-1'},
        ])
        self.assertEqual(self.cliente.find_item('SKU-1')['id'], 2)

    @patch('integrations.alegra.alegra_client.requests.post')
    def test_crea_contacto_y_producto(self, post):
        post.return_value = self._respuesta({'id': 4})
        self.assertEqual(self.cliente.create_contact({'name': 'Ana'}), {'id': 4})
        self.assertTrue(post.call_args.args[0].endswith('/contacts'))
        self.assertEqual(self.cliente.create_item({'name': 'X'}), {'id': 4})
        self.assertTrue(post.call_args.args[0].endswith('/items'))

    @patch('integrations.alegra.alegra_client.requests.delete')
    def test_borra_una_factura(self, delete):
        delete.return_value = self._respuesta({})
        self.cliente.delete_invoice(55)
        self.assertTrue(delete.call_args.args[0].endswith('/invoices/55'))

    def test_el_token_del_entorno_prefiere_alegra_api_token(self):
        with patch.dict(os.environ, {
            'ALEGRA_EMAIL': 'a@b.co', 'ALEGRA_API_TOKEN': 'nuevo', 'ALEGRA_TOKEN': 'viejo',
        }):
            self.assertEqual(AlegraClient().token, 'nuevo')


class MercadoPagoClientTests(SimpleTestCase):
    def setUp(self):
        self.sdk = MagicMock()
        parche = patch.object(mercadopago_client, 'mercadopago', MagicMock(SDK=MagicMock(return_value=self.sdk)))
        parche.start()
        self.addCleanup(parche.stop)

    def test_crea_preferencia_y_devuelve_la_respuesta(self):
        self.sdk.preference.return_value.create.return_value = {'status': 201, 'response': {'id': 'pref-1'}}
        cliente = MercadoPagoClient(access_token='tok')
        self.assertEqual(cliente.create_preference({'items': []}), {'id': 'pref-1'})
        self.sdk.preference.return_value.create.assert_called_once_with({'items': []})

    def test_respuesta_sin_status_se_trata_como_error(self):
        self.sdk.preference.return_value.create.return_value = {}
        with self.assertRaises(MercadoPagoError):
            MercadoPagoClient(access_token='tok').create_preference({})

    def test_un_error_http_del_sdk_lanza_en_vez_de_parecer_un_exito(self):
        # El SDK no lanza ante un 401: devuelve el error dentro del dict.
        self.sdk.preference.return_value.create.return_value = {
            'status': 401, 'response': {'message': 'invalid access token'},
        }
        with self.assertRaisesMessage(MercadoPagoError, 'invalid access token'):
            MercadoPagoClient(access_token='tok').create_preference({})

    def test_consulta_un_pago_por_id(self):
        self.sdk.payment.return_value.get.return_value = {'status': 200, 'response': {'id': 5, 'status': 'approved'}}
        pago = MercadoPagoClient(access_token='tok').get_payment('5')
        self.assertEqual(pago['status'], 'approved')
        self.sdk.payment.return_value.get.assert_called_once_with('5')

    def test_sin_token_no_se_crea_el_cliente(self):
        with patch.dict(os.environ, {'MERCADOPAGO_ACCESS_TOKEN': ''}):
            with self.assertRaises(RuntimeError):
                MercadoPagoClient()

    def test_reembolso_total_no_envia_monto(self):
        self.sdk.refund.return_value.create.return_value = {'status': 201, 'response': {'id': 7}}
        self.assertEqual(MercadoPagoClient(access_token='tok').refund_payment('pay-1'), {'id': 7})
        self.sdk.refund.return_value.create.assert_called_once_with('pay-1', None)

    def test_reembolso_parcial_envia_el_monto(self):
        self.sdk.refund.return_value.create.return_value = {'status': 201, 'response': {}}
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
