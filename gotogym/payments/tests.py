"""Proveedor de pago simulado: creacion de intentos, idempotencia y UI de pruebas."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Order, OrderStatus, PaymentStatus

from .models import PaymentTransaction
from .providers.mock import MockPaymentProvider


def _crear_pedido(total='150000.00'):
    return Order.objects.create(
        order_number=f'GTG-TEST-{Order.objects.count() + 1:04d}',
        email='cliente@example.com',
        phone='3000000000',
        subtotal=Decimal(total),
        total=Decimal(total),
        order_status=OrderStatus.PENDING_PAYMENT,
        payment_status=PaymentStatus.PENDING,
    )


class MockProviderTests(TestCase):
    def setUp(self):
        self.provider = MockPaymentProvider()
        self.pedido = _crear_pedido()

    def test_create_payment_intent_genera_una_transaccion(self):
        transaccion = self.provider.create_payment_intent(self.pedido)
        self.assertEqual(PaymentTransaction.objects.count(), 1)
        self.assertEqual(transaccion.order, self.pedido)
        self.assertEqual(transaccion.provider, 'mock')
        self.assertEqual(transaccion.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(transaccion.amount, self.pedido.total)
        self.assertEqual(transaccion.external_reference, self.pedido.order_number)

    def test_idempotency_key_es_unico_por_intento(self):
        t1 = self.provider.create_payment_intent(self.pedido)
        otro_pedido = _crear_pedido()
        t2 = self.provider.create_payment_intent(otro_pedido)
        self.assertNotEqual(t1.idempotency_key, t2.idempotency_key)

    def test_llamar_dos_veces_mientras_esta_pendiente_no_duplica(self):
        t1 = self.provider.create_payment_intent(self.pedido)
        t2 = self.provider.create_payment_intent(self.pedido)
        self.assertEqual(t1.pk, t2.pk)
        self.assertEqual(PaymentTransaction.objects.count(), 1)

    def test_forzar_el_mismo_estado_dos_veces_no_lo_duplica(self):
        transaccion = self.provider.create_payment_intent(self.pedido)
        self.provider.force_status(transaccion, PaymentTransaction.Status.APPROVED)
        self.provider.force_status(transaccion, PaymentTransaction.Status.APPROVED)

        self.assertEqual(PaymentTransaction.objects.count(), 1)
        transaccion.refresh_from_db()
        self.assertEqual(transaccion.status, PaymentTransaction.Status.APPROVED)

    def test_forzar_aprobado_asigna_payment_id(self):
        transaccion = self.provider.create_payment_intent(self.pedido)
        self.assertEqual(transaccion.payment_id, '')
        self.provider.force_status(transaccion, PaymentTransaction.Status.APPROVED)
        self.assertNotEqual(transaccion.payment_id, '')

    def test_pedido_recien_creado_hasta_aprobado(self):
        transaccion = self.provider.create_payment_intent(self.pedido)
        self.provider.force_status(transaccion, PaymentTransaction.Status.APPROVED)
        transaccion.refresh_from_db()
        self.assertEqual(transaccion.status, PaymentTransaction.Status.APPROVED)

    def test_despues_de_rechazado_un_nuevo_intento_crea_otra_transaccion(self):
        t1 = self.provider.create_payment_intent(self.pedido)
        self.provider.force_status(t1, PaymentTransaction.Status.REJECTED)

        t2 = self.provider.create_payment_intent(self.pedido)
        self.assertNotEqual(t1.pk, t2.pk)
        self.assertEqual(PaymentTransaction.objects.count(), 2)

    def test_no_puede_crearse_un_intento_para_orden_ya_cancelada_sin_transaccion_previa(self):
        # No es una regla del proveedor, pero confirma que create_payment_intent
        # no exige que la orden este en un estado particular: eso lo decide
        # quien la llame.
        self.pedido.order_status = OrderStatus.CANCELLED
        self.pedido.save(update_fields=['order_status'])
        transaccion = self.provider.create_payment_intent(self.pedido)
        self.assertIsNotNone(transaccion)


class PaymentProviderInterfaceTests(TestCase):
    def test_la_interfaz_no_menciona_ningun_proveedor_real(self):
        from .providers.base import PaymentProvider
        import inspect

        fuente = inspect.getsource(PaymentProvider)
        for nombre_prohibido in ['mercadopago', 'MercadoPago', 'stripe', 'Stripe', 'paypal']:
            self.assertNotIn(nombre_prohibido, fuente)


class VistaDePagoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        correo = f'pago-{self._testMethodName[:30]}@example.com'
        self.usuario = User.objects.create_user(email=correo, username=correo, password='secret123')
        self.client.force_login(self.usuario)
        self.pedido = _crear_pedido()
        self.pedido.user = self.usuario
        self.pedido.save(update_fields=['user'])

    def _url_pendiente(self):
        return reverse('payments:pending', args=[self.pedido.order_number])

    def _url_simular(self, status):
        return reverse('payments:simulate', args=[self.pedido.order_number, status])

    @override_settings(DEBUG=True)
    def test_pantalla_de_pago_crea_el_intento_y_muestra_el_total(self):
        response = self.client.get(self._url_pendiente())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.pedido.order_number)
        self.assertEqual(PaymentTransaction.objects.filter(order=self.pedido).count(), 1)

    @override_settings(DEBUG=True)
    def test_los_cuatro_estados_se_pueden_simular_desde_la_ui(self):
        for status in ['pending', 'approved', 'rejected', 'cancelled']:
            response = self.client.post(self._url_simular(status), follow=True)
            self.assertEqual(response.status_code, 200)
            transaccion = PaymentTransaction.objects.get(order=self.pedido)
            self.assertEqual(transaccion.status, status)

    @override_settings(DEBUG=True)
    def test_revisitar_la_pantalla_de_pago_no_crea_una_transaccion_nueva(self):
        # Un GET repetido es solo navegacion: no debe abrir un intento nuevo
        # aunque el intento actual ya haya sido rechazado.
        self.client.post(self._url_simular('rejected'))
        self.assertEqual(PaymentTransaction.objects.filter(order=self.pedido).count(), 1)

        self.client.get(self._url_pendiente())
        self.client.get(self._url_pendiente())
        self.assertEqual(PaymentTransaction.objects.filter(order=self.pedido).count(), 1)

        transaccion = PaymentTransaction.objects.get(order=self.pedido)
        self.assertEqual(transaccion.status, PaymentTransaction.Status.REJECTED)

    @override_settings(DEBUG=True)
    def test_estado_invalido_devuelve_404(self):
        response = self.client.post(self._url_simular('no-existe'))
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False, PAYMENTS_MOCK_UI_ENABLED=False)
    def test_con_debug_falso_y_flag_apagado_la_ui_no_se_muestra(self):
        response = self.client.get(self._url_pendiente())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Simular')

    @override_settings(DEBUG=False, PAYMENTS_MOCK_UI_ENABLED=False)
    def test_con_debug_falso_y_flag_apagado_simular_devuelve_404(self):
        response = self.client.post(self._url_simular('approved'))
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False, PAYMENTS_MOCK_UI_ENABLED=True)
    def test_el_flag_explicito_habilita_la_ui_sin_debug(self):
        response = self.client.get(self._url_pendiente())
        self.assertContains(response, 'Simular')

    def test_no_se_puede_ver_el_pago_de_otro_usuario(self):
        User = get_user_model()
        intruso = User.objects.create_user(
            email='intruso-pago@example.com', username='intruso-pago@example.com', password='secret123',
        )
        self.client.force_login(intruso)
        response = self.client.get(self._url_pendiente())
        self.assertEqual(response.status_code, 404)

    def test_pantalla_de_pago_exige_login(self):
        self.client.logout()
        response = self.client.get(self._url_pendiente())
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)


class IntegracionOrdenPagoTests(TestCase):
    """Order recien creada -> create_payment_intent -> simular approved ->
    PaymentTransaction.status == 'approved' (sin tocar inventario todavia)."""

    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            email='integracion@example.com', username='integracion@example.com', password='secret123',
        )

    @override_settings(DEBUG=True)
    def test_flujo_completo_hasta_aprobado(self):
        pedido = _crear_pedido()
        pedido.user = self.usuario
        pedido.save(update_fields=['user'])

        self.client.force_login(self.usuario)
        self.client.get(reverse('payments:pending', args=[pedido.order_number]))
        self.client.post(reverse('payments:simulate', args=[pedido.order_number, 'approved']))

        transaccion = PaymentTransaction.objects.get(order=pedido)
        self.assertEqual(transaccion.status, PaymentTransaction.Status.APPROVED)

        # El pago aprobado dispara confirm_payment: sin lineas que descontar
        # (este pedido se creo a mano, sin OrderItem), la confirmacion es
        # trivial pero real.
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(pedido.payment_status, PaymentStatus.APPROVED)
