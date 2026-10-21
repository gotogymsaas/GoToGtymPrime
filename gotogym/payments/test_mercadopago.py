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
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from integrations.mercadopago.mercadopago_client import MercadoPagoError
from inventory.models import Inventory
from orders.models import OrderStatus
from orders.services import create_order_from_cart
from products.models import Brand, Product, ProductCategory, ProductVariant

from .models import PaymentTransaction
from .providers.mercadopago import MercadoPagoPaymentProvider
from .signature import (
    build_signature_template,
    compute_signature,
    parse_x_signature,
    verify_signature,
)

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

    def __init__(self, response=None, refund_response=None, payments=None):
        self.response = response or {
            'id': 'pref-fake-123',
            'init_point': 'https://www.mercadopago.com.co/checkout/v1/redirect?pref_id=pref-fake-123',
        }
        self.refund_response = refund_response or {'id': 'refund-fake-1', 'status': 'approved'}
        self.payments = payments if payments is not None else {}
        self.llamadas = []
        self.llamadas_refund = []

    def get_payment(self, payment_id):
        if isinstance(self.payments, Exception):
            raise self.payments
        return self.payments[str(payment_id)]

    def create_preference(self, preference_data):
        self.llamadas.append(preference_data)
        return self.response

    def refund_payment(self, payment_id, amount=None):
        self.llamadas_refund.append({'payment_id': payment_id, 'amount': amount})
        return self.refund_response


def _pago(pedido, status, payment_id='pay-abc-1', amount=None, currency='COP'):
    """Lo que devolveria `GET /v1/payments/{id}` de Mercado Pago."""
    return {
        'id': payment_id,
        'status': status,
        'external_reference': pedido.order_number,
        'transaction_amount': float(pedido.total if amount is None else amount),
        'currency_id': currency,
    }


class MercadoPagoProviderTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoría MP')
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
        self.assertIn('Envío', titulos)

        item_envio = next(item for item in preferencia_enviada['items'] if item['title'] == 'Envío')
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
        self.assertNotIn('Envío', titulos)

    def test_llamar_dos_veces_mientras_esta_pendiente_no_duplica(self):
        cliente_falso = FakeMercadoPagoClient()
        provider = MercadoPagoPaymentProvider(client=cliente_falso)

        t1 = provider.create_payment_intent(self.pedido)
        t2 = provider.create_payment_intent(self.pedido)

        self.assertEqual(t1.pk, t2.pk)
        self.assertEqual(len(cliente_falso.llamadas), 1)

    def test_con_descuento_se_cobra_un_solo_item_por_el_total_real(self):
        # Mercado Pago no admite items negativos: sin esto el comprador
        # pagaria el total sin el descuento del cupon.
        self.pedido.discount_total = Decimal('10000.00')
        self.pedido.total = self.pedido.total - Decimal('10000.00')
        self.pedido.save(update_fields=['discount_total', 'total'])

        cliente_falso = FakeMercadoPagoClient()
        MercadoPagoPaymentProvider(client=cliente_falso).create_payment_intent(self.pedido)

        items = cliente_falso.llamadas[0]['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(Decimal(str(items[0]['unit_price'])), self.pedido.total)

    @override_settings(SITIO_URL='https://gotogym.store')
    def test_con_https_la_preferencia_trae_retorno_automatico_y_webhook(self):
        cliente_falso = FakeMercadoPagoClient()
        MercadoPagoPaymentProvider(client=cliente_falso).create_payment_intent(self.pedido)

        preferencia = cliente_falso.llamadas[0]
        self.assertEqual(preferencia['auto_return'], 'approved')
        self.assertEqual(preferencia['notification_url'], 'https://gotogym.store/pagos/webhook/mercadopago/')
        self.assertTrue(preferencia['back_urls']['success'].startswith('https://gotogym.store/'))
        self.assertIn(self.pedido.order_number, preferencia['back_urls']['success'])

    @override_settings(SITIO_URL='http://127.0.0.1:8000')
    def test_en_local_http_no_se_piden_auto_return_ni_webhook(self):
        cliente_falso = FakeMercadoPagoClient()
        MercadoPagoPaymentProvider(client=cliente_falso).create_payment_intent(self.pedido)

        preferencia = cliente_falso.llamadas[0]
        self.assertNotIn('auto_return', preferencia)
        self.assertNotIn('notification_url', preferencia)
        self.assertIn('success', preferencia['back_urls'])

    def test_checkout_url_sale_del_init_point_de_la_preferencia(self):
        provider = MercadoPagoPaymentProvider(client=FakeMercadoPagoClient())
        transaccion = provider.create_payment_intent(self.pedido)
        self.assertIn('pref_id=pref-fake-123', provider.checkout_url(transaccion))


class HandleCallbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoría callback')
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
        self.cliente_falso = FakeMercadoPagoClient()
        self.provider = MercadoPagoPaymentProvider(client=self.cliente_falso)
        self.transaccion = self.provider.create_payment_intent(self.pedido)

    def _payload(self, status, payment_id='pay-abc-1', **kwargs):
        # El aviso solo trae el id; el estado sale de consultar el pago.
        self.cliente_falso.payments[payment_id] = _pago(self.pedido, status, payment_id, **kwargs)
        return {'type': 'payment', 'data': {'id': payment_id}}

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
        self.cliente_falso.payments['pago-que-no-existe'] = {
            'id': 'pago-que-no-existe', 'status': 'approved', 'external_reference': 'GTG-NO-EXISTE',
            'transaction_amount': 1.0, 'currency_id': 'COP',
        }
        with self.assertRaises(PaymentTransaction.DoesNotExist):
            self.provider.handle_callback({'data': {'id': 'pago-que-no-existe'}})

    def test_un_importe_distinto_al_cobrado_no_aprueba_el_pago(self):
        payload = self._payload('approved', amount=self.pedido.total - Decimal('1.00'))
        transaccion = self.provider.handle_callback(payload)
        self.assertEqual(transaccion.status, PaymentTransaction.Status.PENDING)

    def test_una_moneda_distinta_a_la_cobrada_no_aprueba_el_pago(self):
        payload = self._payload('approved', currency='USD')
        transaccion = self.provider.handle_callback(payload)
        self.assertEqual(transaccion.status, PaymentTransaction.Status.PENDING)

    def test_aplicar_un_pago_conserva_la_preferencia_con_su_init_point(self):
        transaccion = self.provider.handle_callback(self._payload('rejected'))
        self.assertIn('init_point', transaccion.raw_payload)
        self.assertEqual(transaccion.raw_payload['payment']['status'], 'rejected')

    def test_un_pago_rechazado_puede_pasar_a_aprobado_al_reintentar(self):
        self.provider.handle_callback(self._payload('rejected', payment_id='pay-1'))
        transaccion = self.provider.handle_callback(self._payload('approved', payment_id='pay-2'))
        self.assertEqual(transaccion.status, PaymentTransaction.Status.APPROVED)
        self.assertEqual(transaccion.payment_id, 'pay-2')

    def test_notificacion_sin_id_de_pago_lanza_does_not_exist(self):
        with self.assertRaises(PaymentTransaction.DoesNotExist):
            self.provider.handle_callback({'type': 'payment'})


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
        categoria = ProductCategory.objects.create(name='Categoría webhook')
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

        self.cliente_falso = FakeMercadoPagoClient()
        self.provider = MercadoPagoPaymentProvider(client=self.cliente_falso)
        self.transaccion = self.provider.create_payment_intent(self.pedido)
        # La vista crea su propio proveedor: se le entrega el que usa el doble.
        parche = mock.patch('payments.views.MercadoPagoPaymentProvider', return_value=self.provider)
        parche.start()
        self.addCleanup(parche.stop)

        self.client = Client()
        self.secret = 'webhook-secret-de-prueba'

    def _aviso(self, status, payment_id='pay-webhook-1'):
        """Registra el pago en el doble y devuelve el aviso (solo trae el id)."""
        self.cliente_falso.payments[payment_id] = _pago(self.pedido, status, payment_id)
        return {'type': 'payment', 'data': {'id': payment_id}}

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
        response = self._post_firmado(self._aviso('approved'))

        self.assertEqual(response.status_code, 200)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(Inventory.objects.get(variant=self.variante).quantity_available, 3)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='webhook-secret-de-prueba')
    def test_notificacion_duplicada_no_descuenta_stock_dos_veces(self):
        payload = self._aviso('approved')
        self._post_firmado(payload)
        self._post_firmado(payload)

        self.assertEqual(Inventory.objects.get(variant=self.variante).quantity_available, 3)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='webhook-secret-de-prueba')
    def test_el_estado_del_cuerpo_del_aviso_se_ignora(self):
        # Solo cuenta lo que Mercado Pago responde al consultar el pago: un
        # cuerpo que diga "approved" no aprueba nada por si solo.
        self.cliente_falso.payments['pay-webhook-1'] = _pago(self.pedido, 'rejected', 'pay-webhook-1')
        aviso = {'type': 'payment', 'data': {'id': 'pay-webhook-1'}, 'status': 'approved'}

        self._post_firmado(aviso)

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.PENDING_PAYMENT)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='webhook-secret-de-prueba')
    def test_avisos_de_otros_temas_se_acusan_sin_consultar_nada(self):
        response = self._post_firmado({'type': 'merchant_order', 'data': {'id': 'pay-webhook-1'}})
        self.assertEqual(response.status_code, 200)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.PENDING_PAYMENT)

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='webhook-secret-de-prueba')
    def test_si_mercado_pago_no_responde_se_pide_reintento(self):
        self.cliente_falso.payments = MercadoPagoError('caido')
        response = self._post_firmado({'type': 'payment', 'data': {'id': 'pay-webhook-1'}})
        self.assertEqual(response.status_code, 502)

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
        payload = self._aviso('pending', payment_id='pay-webhook-2')
        response = self._post_firmado(payload, payment_id='pay-webhook-2')
        self.assertEqual(response.status_code, 200)


class PaymentReturnViewTests(TestCase):
    """Vista a la que vuelve el comprador desde Mercado Pago."""

    def setUp(self):
        categoria = ProductCategory.objects.create(name='Categoría retorno')
        marca = Brand.objects.create(name='Marca retorno')
        producto = Product.objects.create(
            name='Producto retorno', category=categoria, brand=marca,
            base_price=Decimal('80000.0000'), stock=0,
        )
        self.variante = _crear_variante(producto, 'MP-004-S-NEG', 'S', 'negro', 5)
        User = get_user_model()
        self.usuario = User.objects.create_user(
            email='mp-retorno@example.com', username='mp-retorno@example.com', password='secret123',
        )
        self.pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)

        self.cliente_falso = FakeMercadoPagoClient()
        self.provider = MercadoPagoPaymentProvider(client=self.cliente_falso)
        self.provider.create_payment_intent(self.pedido)
        parche = mock.patch('payments.views.MercadoPagoPaymentProvider', return_value=self.provider)
        parche.start()
        self.addCleanup(parche.stop)

        self.client = Client()
        self.client.force_login(self.usuario)
        self.url = reverse('payments:return', args=[self.pedido.order_number])

    def _volver(self, status, payment_id='123456'):
        self.cliente_falso.payments[payment_id] = _pago(self.pedido, status, payment_id)
        # Lo que trae la URL lo puede escribir cualquiera: solo cuenta el id.
        return self.client.get(self.url, {'payment_id': payment_id, 'status': 'approved'})

    @override_settings(PAYMENT_PROVIDER='mercadopago')
    def test_pago_aprobado_confirma_el_pedido_sin_esperar_al_webhook(self):
        respuesta = self._volver('approved')

        self.assertRedirects(
            respuesta, reverse('orders:order_detail', args=[self.pedido.order_number]),
            fetch_redirect_response=False,
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.CONFIRMED)

    @override_settings(PAYMENT_PROVIDER='mercadopago')
    def test_el_status_de_la_url_no_aprueba_si_mercado_pago_dice_otra_cosa(self):
        respuesta = self._volver('rejected')

        self.assertRedirects(
            respuesta, reverse('payments:pending', args=[self.pedido.order_number]),
            fetch_redirect_response=False,
        )
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.PENDING_PAYMENT)

    @override_settings(PAYMENT_PROVIDER='mercadopago')
    def test_pago_en_proceso_vuelve_a_la_pagina_de_pago(self):
        respuesta = self._volver('in_process')
        self.assertRedirects(
            respuesta, reverse('payments:pending', args=[self.pedido.order_number]),
            fetch_redirect_response=False,
        )

    @override_settings(PAYMENT_PROVIDER='mercadopago')
    def test_un_pago_de_otro_pedido_no_confirma_este(self):
        otro = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        otro_proveedor_cliente = FakeMercadoPagoClient()
        self.provider = MercadoPagoPaymentProvider(client=otro_proveedor_cliente)
        self.provider.create_payment_intent(otro)
        otro_proveedor_cliente.payments['999'] = _pago(otro, 'approved', '999')

        with mock.patch('payments.views.MercadoPagoPaymentProvider', return_value=self.provider):
            self.client.get(self.url, {'payment_id': '999'})

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.PENDING_PAYMENT)

    @override_settings(PAYMENT_PROVIDER='mercadopago')
    def test_sin_payment_id_solo_vuelve_a_la_pagina_de_pago(self):
        respuesta = self.client.get(self.url)
        self.assertRedirects(
            respuesta, reverse('payments:pending', args=[self.pedido.order_number]),
            fetch_redirect_response=False,
        )

    @override_settings(PAYMENT_PROVIDER='mercadopago')
    def test_si_mercado_pago_falla_no_rompe_la_pagina(self):
        self.cliente_falso.payments = MercadoPagoError('caido')
        respuesta = self.client.get(self.url, {'payment_id': '123456'})
        self.assertEqual(respuesta.status_code, 302)

    @override_settings(PAYMENT_PROVIDER='mercadopago', DEBUG=True)
    def test_la_pagina_de_pago_ofrece_ir_a_mercado_pago_y_oculta_la_simulacion(self):
        respuesta = self.client.get(reverse('payments:pending', args=[self.pedido.order_number]))

        self.assertContains(respuesta, 'pref_id=pref-fake-123')
        self.assertContains(respuesta, 'Pagar con Mercado Pago')
        self.assertNotContains(respuesta, 'Herramienta de pruebas')

    @override_settings(PAYMENT_PROVIDER='mercadopago')
    def test_si_no_se_puede_crear_la_preferencia_no_se_rompe_la_pagina(self):
        otro = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        self.provider._client = mock.Mock(create_preference=mock.Mock(side_effect=MercadoPagoError('sin red')))

        respuesta = self.client.get(reverse('payments:pending', args=[otro.order_number]))

        self.assertRedirects(
            respuesta, reverse('orders:order_detail', args=[otro.order_number]), fetch_redirect_response=False,
        )

    def test_requiere_sesion_y_que_el_pedido_sea_del_usuario(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

        User = get_user_model()
        ajeno = User.objects.create_user(email='ajeno@example.com', username='ajeno@example.com', password='secret123')
        self.client.force_login(ajeno)
        self.assertEqual(self.client.get(self.url, {'payment_id': '1'}).status_code, 404)


class MercadoPagoRefundTestCase(TestCase):
    """`refund_payment`: preparado, no activo (mismo espiritu que el resto
    del proveedor real)."""

    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoría MP reembolso')
        marca = Brand.objects.create(name='Marca MP reembolso')
        producto = Product.objects.create(
            name='Producto MP reembolso', category=categoria, brand=marca,
            base_price=Decimal('100000.0000'), stock=0,
        )
        variante = _crear_variante(producto, 'MP-REF-001-S-NEG', 'S', 'negro', 5)
        User = get_user_model()
        usuario = User.objects.create_user(
            email='mp-reembolso@example.com', username='mp-reembolso@example.com', password='secret123',
        )
        cls.pedido = create_order_from_cart(usuario, {str(variante.pk): 1}, DATOS)

    def _transaccion_aprobada(self, payment_id='pay-aprobado-1'):
        return PaymentTransaction.objects.create(
            order=self.pedido, provider='mercadopago', payment_id=payment_id,
            external_reference=self.pedido.order_number,
            status=PaymentTransaction.Status.APPROVED, amount=self.pedido.total,
            idempotency_key='idem-refund-1',
        )

    def test_refund_payment_llama_al_cliente_con_el_payment_id(self):
        transaccion = self._transaccion_aprobada()
        cliente_falso = FakeMercadoPagoClient()
        provider = MercadoPagoPaymentProvider(client=cliente_falso)

        resultado = provider.refund_payment(transaccion)

        self.assertEqual(cliente_falso.llamadas_refund[0]['payment_id'], 'pay-aprobado-1')
        self.assertEqual(resultado['status'], 'approved')
        self.assertEqual(resultado['provider_refund_id'], 'refund-fake-1')

    def test_refund_parcial_envia_el_monto(self):
        transaccion = self._transaccion_aprobada()
        cliente_falso = FakeMercadoPagoClient()
        provider = MercadoPagoPaymentProvider(client=cliente_falso)

        provider.refund_payment(transaccion, amount=Decimal('5000.00'))

        self.assertEqual(cliente_falso.llamadas_refund[0]['amount'], 5000.0)

    def test_no_se_puede_reembolsar_un_pago_que_nunca_se_aprobo(self):
        transaccion = PaymentTransaction.objects.create(
            order=self.pedido, provider='mercadopago', payment_id='',
            external_reference=self.pedido.order_number,
            status=PaymentTransaction.Status.PENDING, amount=self.pedido.total,
            idempotency_key='idem-refund-2',
        )
        provider = MercadoPagoPaymentProvider(client=FakeMercadoPagoClient())

        with self.assertRaises(ValueError):
            provider.refund_payment(transaccion)
