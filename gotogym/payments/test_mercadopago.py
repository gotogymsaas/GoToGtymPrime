"""Arquitectura de Mercado Pago real: preparada, no activa.

No se conecta a ningun servidor real de Mercado Pago: el cliente se
sustituye por un doble en memoria. Verifica la interfaz, la correccion del
bug historico de envio, la validacion de firma del webhook, y su
idempotencia.
"""
import hashlib
import hmac
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventory.models import Inventory
from orders.models import Order, OrderStatus
from orders.services import create_order_from_cart
from products.models import Brand, Product, ProductCategory, ProductVariant

from .models import PaymentTransaction
from .providers.mercadopago import MercadoPagoPaymentProvider
from .signature import build_signature_template, compute_signature, parse_x_signature, verify_signature

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class FakeMercadoPagoClient:
    """Doble de MercadoPagoClient: no hace ninguna llamada de red."""

    def __init__(self, response=None):
        self.response = response or {'id': 'pref-fake-123'}
        self.llamadas = []

    def create_preference(self, preference_data):
        self.llamadas.append(preference_data)
        return self.response


class MercadoPagoProviderTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria MP')
        marca = Brand.objects.create(name='Marca MP')
        cls.producto = Product.objects.create(
            name='Producto MP', category=categoria, brand=marca,
            base_price=Decimal('100000.0000'), stock=0,
        )
        cls.variante = _crear_variante(cls.producto, 'MP-001-S-NEG', 'S', 'negro', 5)

        User = get_user_model()
        cls.usuario = User.objects.create_user(
            email='mp-cliente@example.com', username='mp-cliente@example.com', password='secret123',
        )
        cls.pedido = create_order_from_cart(cls.usuario, {str(cls.variante.pk): 2}, DATOS)

    def test_la_interfaz_no_tiene_referencias_a_otro_proveedor(self):
        import inspect

        fuente = inspect.getsource(MercadoPagoPaymentProvider.create_payment_intent)
        # Solo puede mencionar a su propio proveedor, no a otro.
        self.assertNotIn('stripe', fuente.lower())
        self.assertNotIn('paypal', fuente.lower())

    def test_create_payment_intent_incluye_el_envio_como_item(self):
        # Este es el bug historico explicito: el envio se mostraba en el
        # carrito y en la Order, pero nunca llegaba a la preferencia de
        # Mercado Pago. Aqui debe aparecer como un item mas.
        cliente_falso = FakeMercadoPagoClient()
        provider = MercadoPagoPaymentProvider(client=cliente_falso)

        provider.create_payment_intent(self.pedido)

        preferencia_enviada = cliente_falso.llamadas[0]
        titulos = [item['title'] for item in preferencia_enviada['items']]
        self.assertIn('Envio', titulos)

        item_envio = next(item for item in preferencia_enviada['items'] if item['title'] == 'Envio')
        self.assertEqual(Decimal(str(item_envio['unit_price'])), self.pedido.shipping_cost)

    def test_la_suma_de_los_items_coincide_con_el_total_de_la_orden(self):
        cliente_falso = FakeMercadoPagoClient()
        provider = MercadoPagoPaymentProvider(client=cliente_falso)
        provider.create_payment_intent(self.pedido)

        preferencia_enviada = cliente_falso.llamadas[0]
        suma = sum(Decimal(str(i['unit_price'])) * i['quantity'] for i in preferencia_enviada['items'])
        self.assertEqual(suma, self.pedido.total)

    def test_external_reference_es_el_order_number_desde_el_primer_intento(self):
        cliente_falso = FakeMercadoPagoClient()
        provider = MercadoPagoPaymentProvider(client=cliente_falso)
        transaccion = provider.create_payment_intent(self.pedido)

        self.assertEqual(transaccion.external_reference, self.pedido.order_number)
        self.assertEqual(cliente_falso.llamadas[0]['external_reference'], self.pedido.order_number)

    def test_no_sin_envio_no_agrega_el_item(self):
        self.pedido.shipping_cost = Decimal('0.00')
        self.pedido.save(update_fields=['shipping_cost'])

        cliente_falso = FakeMercadoPagoClient()
        provider = MercadoPagoPaymentProvider(client=cliente_falso)
        provider.create_payment_intent(self.pedido)

        titulos = [item['title'] for item in cliente_falso.llamadas[0]['items']]
        self.assertNotIn('Envio', titulos)

    def test_llamar_dos_veces_mientras_esta_pendiente_no_duplica(self):
        cliente_falso = FakeMercadoPagoClient()
        provider = MercadoPagoPaymentProvider(client=cliente_falso)

        t1 = provider.create_payment_intent(self.pedido)
        t2 = provider.create_payment_intent(self.pedido)

        self.assertEqual(t1.pk, t2.pk)
        self.assertEqual(len(cliente_falso.llamadas), 1)


class HandleCallbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria callback')
        marca = Brand.objects.create(name='Marca callback')
        producto = Product.objects.create(
            name='Producto callback', category=categoria, brand=marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        cls.variante = _crear_variante(producto, 'MP-002-S-NEG', 'S', 'negro', 5)

        User = get_user_model()
        cls.usuario = User.objects.create_user(
            email='mp-callback@example.com', username='mp-callback@example.com', password='secret123',
        )
        cls.pedido = create_order_from_cart(cls.usuario, {str(cls.variante.pk): 1}, DATOS)

    def setUp(self):
        cliente_falso = FakeMercadoPagoClient()
        self.provider = MercadoPagoPaymentProvider(client=cliente_falso)
        self.transaccion = self.provider.create_payment_intent(self.pedido)

    def _payload(self, status, payment_id='pay-abc-1'):
        return {
            'data': {'id': payment_id},
            'external_reference': self.pedido.order_number,
            'status': status,
        }

    def test_aprobado_actualiza_el_estado_y_el_payment_id(self):
        transaccion = self.provider.handle_callback(self._payload('approved'))
        self.assertEqual(transaccion.status, PaymentTransaction.Status.APPROVED)
        self.assertEqual(transaccion.payment_id, 'pay-abc-1')

    def test_rechazado_se_mapea_correctamente(self):
        transaccion = self.provider.handle_callback(self._payload('rejected'))
        self.assertEqual(transaccion.status, PaymentTransaction.Status.REJECTED)

    def test_estado_no_reconocido_no_cambia_nada(self):
        antes = self.transaccion.status
        transaccion = self.provider.handle_callback(self._payload('some_future_status_mp_invente'))
        self.assertEqual(transaccion.status, antes)

    def test_notificacion_repetida_con_mismo_payment_id_no_reprocesa(self):
        self.provider.handle_callback(self._payload('approved'))
        self.transaccion.refresh_from_db()
        actualizado_en_1 = self.transaccion.updated_at

        self.provider.handle_callback(self._payload('approved'))
        self.transaccion.refresh_from_db()

        self.assertEqual(self.transaccion.updated_at, actualizado_en_1)

    def test_payload_sin_transaccion_correspondiente_lanza_does_not_exist(self):
        payload = {'data': {'id': 'pago-que-no-existe'}, 'external_reference': 'GTG-NO-EXISTE', 'status': 'approved'}
        with self.assertRaises(PaymentTransaction.DoesNotExist):
            self.provider.handle_callback(payload)


class SignatureTests(TestCase):
    """Contra payloads simulados, siguiendo el esquema documentado
    oficialmente (HMAC-SHA256 sobre id/request-id/ts). Sin credenciales de
    sandbox reales para validar contra un webhook autentico."""

    def test_parse_x_signature_extrae_ts_y_v1(self):
        ts, v1 = parse_x_signature('ts=1700000000,v1=abcdef123456')
        self.assertEqual(ts, '1700000000')
        self.assertEqual(v1, 'abcdef123456')

    def test_parse_x_signature_vacio_no_rompe(self):
        ts, v1 = parse_x_signature('')
        self.assertIsNone(ts)
        self.assertIsNone(v1)

    def test_template_omite_componentes_ausentes(self):
        template = build_signature_template(None, 'req-1', '123')
        # 'id:' es tambien substring de 'request-id:', asi que se verifica
        # que el componente de data_id no aparece como token propio (al
        # inicio del template, que es donde va cuando si esta presente).
        self.assertFalse(template.startswith('id:'))
        self.assertIn('request-id:req-1;', template)
        self.assertIn('ts:123;', template)

    def test_template_incluye_id_cuando_esta_presente(self):
        template = build_signature_template('42', 'req-1', '123')
        self.assertTrue(template.startswith('id:42;'))

    def test_firma_valida_se_acepta(self):
        secret = 'un-secreto-de-prueba'
        template_esperado = build_signature_template('987654321', 'req-1', '1700000000')
        v1 = hmac.new(secret.encode(), template_esperado.encode(), hashlib.sha256).hexdigest()

        factory = RequestFactory()
        request = factory.post(
            '/pagos/webhook/mercadopago/?data.id=987654321',
            HTTP_X_SIGNATURE=f'ts=1700000000,v1={v1}',
            HTTP_X_REQUEST_ID='req-1',
        )
        self.assertTrue(verify_signature(request, secret))

    def test_firma_con_secreto_incorrecto_se_rechaza(self):
        secret = 'un-secreto-de-prueba'
        v1 = compute_signature('987654321', 'req-1', '1700000000', 'otro-secreto')

        factory = RequestFactory()
        request = factory.post(
            '/pagos/webhook/mercadopago/?data.id=987654321',
            HTTP_X_SIGNATURE=f'ts=1700000000,v1={v1}',
            HTTP_X_REQUEST_ID='req-1',
        )
        self.assertFalse(verify_signature(request, secret))

    def test_sin_header_x_signature_se_rechaza(self):
        factory = RequestFactory()
        request = factory.post('/pagos/webhook/mercadopago/')
        self.assertFalse(verify_signature(request, 'cualquier-secreto'))

    def test_sin_secreto_configurado_se_rechaza_aunque_la_firma_parezca_valida(self):
        factory = RequestFactory()
        request = factory.post(
            '/pagos/webhook/mercadopago/',
            HTTP_X_SIGNATURE='ts=1,v1=loquesea',
        )
        self.assertFalse(verify_signature(request, ''))


class MercadoPagoWebhookViewTests(TestCase):
    def setUp(self):
        categoria = ProductCategory.objects.create(name='Categoria webhook')
        marca = Brand.objects.create(name='Marca webhook')
        producto = Product.objects.create(
            name='Producto webhook', category=categoria, brand=marca,
            base_price=Decimal('70000.0000'), stock=0,
        )
        self.variante = _crear_variante(producto, 'MP-003-S-NEG', 'S', 'negro', 5)

        User = get_user_model()
        self.usuario = User.objects.create_user(
            email='mp-webhook@example.com', username='mp-webhook@example.com', password='secret123',
        )
        self.pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 2}, DATOS)

        cliente_falso = FakeMercadoPagoClient()
        self.provider = MercadoPagoPaymentProvider(client=cliente_falso)
        self.transaccion = self.provider.create_payment_intent(self.pedido)

        self.client = Client()
        self.secret = 'webhook-secret-de-prueba'

    def _post_firmado(self, payload, payment_id='pay-webhook-1'):
        ts = '1700000000'
        request_id = 'req-webhook-1'
        v1 = compute_signature(payment_id, request_id, ts, self.secret)
        return self.client.post(
            reverse('mercadopago_webhook') + f'?data.id={payment_id}',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_SIGNATURE=f'ts={ts},v1={v1}',
            HTTP_X_REQUEST_ID=request_id,
        )

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='webhook-secret-de-prueba')
    def test_webhook_con_firma_valida_aprueba_y_confirma_el_pedido(self):
        payload = {
            'data': {'id': 'pay-webhook-1'},
            'external_reference': self.pedido.order_number,
            'status': 'approved',
        }
        response = self._post_firmado(payload)

        self.assertEqual(response.status_code, 200)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(Inventory.objects.get(variant=self.variante).quantity_available, 3)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='webhook-secret-de-prueba')
    def test_notificacion_duplicada_no_descuenta_stock_dos_veces(self):
        payload = {
            'data': {'id': 'pay-webhook-1'},
            'external_reference': self.pedido.order_number,
            'status': 'approved',
        }
        self._post_firmado(payload)
        self._post_firmado(payload)

        self.assertEqual(Inventory.objects.get(variant=self.variante).quantity_available, 3)

    def test_webhook_sin_secreto_configurado_se_rechaza(self):
        payload = {'data': {'id': 'x'}, 'external_reference': self.pedido.order_number, 'status': 'approved'}
        response = self._post_firmado(payload)
        self.assertEqual(response.status_code, 403)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='el-secreto-correcto')
    def test_webhook_con_firma_incorrecta_se_rechaza(self):
        ts = '1700000000'
        v1_incorrecto = compute_signature('pay-x', 'req-1', ts, 'secreto-equivocado')
        response = self.client.post(
            reverse('mercadopago_webhook') + '?data.id=pay-x',
            data=json.dumps({'status': 'approved'}),
            content_type='application/json',
            HTTP_X_SIGNATURE=f'ts={ts},v1={v1_incorrecto}',
            HTTP_X_REQUEST_ID='req-1',
        )
        self.assertEqual(response.status_code, 403)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.PENDING_PAYMENT)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='webhook-secret-de-prueba')
    def test_get_no_esta_permitido(self):
        response = self.client.get(reverse('mercadopago_webhook'))
        self.assertEqual(response.status_code, 405)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='webhook-secret-de-prueba')
    def test_webhook_no_exige_login_ni_csrf(self):
        # Un webhook lo llama el servidor de Mercado Pago, no un navegador
        # con sesion: sin cliente autenticado y sin token CSRF, la firma
        # valida debe bastar para que la peticion se procese.
        payload = {
            'data': {'id': 'pay-webhook-2'},
            'external_reference': self.pedido.order_number,
            'status': 'pending',
        }
        response = self._post_firmado(payload, payment_id='pay-webhook-2')
        self.assertEqual(response.status_code, 200)
