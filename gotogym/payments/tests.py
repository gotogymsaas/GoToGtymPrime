"""Proveedor de pago simulado: creacion de intentos, idempotencia y UI de pruebas."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from orders.models import Order, OrderStatus, PaymentStatus

from .models import PaymentTransaction, Refund
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
        import inspect

        from .providers.base import PaymentProvider

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


class RefundServiceTests(TestCase):
    """`refund_order_payment`: reembolso real via el proveedor que proceso
    el pago original."""

    def setUp(self):
        self.pedido = _crear_pedido()
        User = get_user_model()
        self.admin = User.objects.create_user(
            email='admin-reembolso@example.com', username='admin-reembolso@example.com',
            password='secret123', is_staff=True,
        )

    def _transaccion_aprobada(self):
        return PaymentTransaction.objects.create(
            order=self.pedido, provider='mock', payment_id='mock-pay-1',
            external_reference=self.pedido.order_number,
            status=PaymentTransaction.Status.APPROVED, amount=self.pedido.total,
            idempotency_key='idem-refund-service-1',
        )

    def test_reembolso_exitoso_crea_registro_aprobado(self):
        from .services import refund_order_payment

        transaccion = self._transaccion_aprobada()
        reembolso = refund_order_payment(self.pedido, self.admin)

        self.assertEqual(reembolso.status, Refund.Status.APPROVED)
        self.assertEqual(reembolso.amount, transaccion.amount)
        self.assertEqual(reembolso.requested_by, self.admin)

    def test_un_rechazo_del_proveedor_deja_un_reembolso_fallido(self):
        from unittest.mock import patch

        from .providers.base import RefundRejected
        from .services import RefundError, refund_order_payment

        transaccion = self._transaccion_aprobada()
        with patch(
            'payments.providers.mock.MockPaymentProvider.refund_payment',
            side_effect=RefundRejected('saldo insuficiente'),
        ):
            with self.assertRaises(RefundError):
                refund_order_payment(self.pedido, self.admin)

        reembolso = transaccion.refunds.get()
        self.assertEqual(reembolso.status, Refund.Status.FAILED)
        self.assertIn('saldo insuficiente', reembolso.error_message)

    def test_tras_un_rechazo_se_puede_volver_a_intentar(self):
        from unittest.mock import patch

        from .providers.base import RefundRejected
        from .services import RefundError, refund_order_payment

        transaccion = self._transaccion_aprobada()
        with patch(
            'payments.providers.mock.MockPaymentProvider.refund_payment',
            side_effect=RefundRejected('rechazado'),
        ):
            with self.assertRaises(RefundError):
                refund_order_payment(self.pedido, self.admin)

        reembolso = refund_order_payment(self.pedido, self.admin)

        self.assertEqual(reembolso.status, Refund.Status.APPROVED)
        self.assertEqual(transaccion.refunds.count(), 2)

    def test_un_estado_rechazado_del_proveedor_queda_como_fallido(self):
        from unittest.mock import patch

        from .services import RefundError, refund_order_payment

        transaccion = self._transaccion_aprobada()
        with patch(
            'payments.providers.mock.MockPaymentProvider.refund_payment',
            return_value={'provider_refund_id': 'r-1', 'status': 'rejected'},
        ):
            with self.assertRaises(RefundError):
                refund_order_payment(self.pedido, self.admin)

        self.assertEqual(transaccion.refunds.get().status, Refund.Status.FAILED)

    def test_un_error_ambiguo_deja_el_reembolso_pendiente_y_bloquea_otro(self):
        from unittest.mock import patch

        from .services import RefundError, refund_order_payment

        transaccion = self._transaccion_aprobada()
        with patch(
            'payments.providers.mock.MockPaymentProvider.refund_payment',
            side_effect=TimeoutError('tiempo agotado'),
        ):
            with self.assertRaises(RefundError):
                refund_order_payment(self.pedido, self.admin)

        reembolso = transaccion.refunds.get()
        self.assertEqual(reembolso.status, Refund.Status.PENDING)
        self.assertIn('tiempo agotado', reembolso.error_message)
        with self.assertRaises(RefundError):
            refund_order_payment(self.pedido, self.admin)
        self.assertEqual(transaccion.refunds.count(), 1)

    def test_un_reembolso_pendiente_impide_pedir_otro(self):
        from unittest.mock import patch

        from .services import RefundError, refund_order_payment

        transaccion = self._transaccion_aprobada()
        Refund.objects.create(
            payment_transaction=transaccion, amount=transaccion.amount, status=Refund.Status.PENDING,
        )
        with patch('payments.providers.mock.MockPaymentProvider.refund_payment') as llamada:
            with self.assertRaises(RefundError):
                refund_order_payment(self.pedido, self.admin)
        llamada.assert_not_called()

    def test_la_llamada_al_proveedor_ocurre_fuera_de_la_transaccion_y_con_clave(self):
        from unittest.mock import patch

        from django.db import connection

        from .services import refund_order_payment

        self._transaccion_aprobada()
        vistos = {}

        def espia(self_provider, transaccion, amount=None, idempotency_key=None):
            # La prueba ya corre dentro de una transaccion; un `atomic` propio
            # del servicio abriria un punto de guardado encima.
            vistos['puntos_de_guardado'] = len(connection.savepoint_ids)
            vistos['clave'] = idempotency_key
            return {'provider_refund_id': 'r-1', 'status': 'approved'}

        base = len(connection.savepoint_ids)
        with patch('payments.providers.mock.MockPaymentProvider.refund_payment', espia):
            reembolso = refund_order_payment(self.pedido, self.admin)

        self.assertEqual(vistos['puntos_de_guardado'], base)
        self.assertTrue(vistos['clave'])
        self.assertEqual(vistos['clave'], reembolso.idempotency_key)

    def test_no_se_puede_reembolsar_sin_pago_aprobado(self):
        from .services import RefundError, refund_order_payment

        with self.assertRaises(RefundError):
            refund_order_payment(self.pedido, self.admin)

    def test_no_se_puede_reembolsar_dos_veces(self):
        from .services import RefundError, refund_order_payment

        self._transaccion_aprobada()
        refund_order_payment(self.pedido, self.admin)

        with self.assertRaises(RefundError):
            refund_order_payment(self.pedido, self.admin)

    def test_no_se_puede_reembolsar_mas_de_lo_pagado(self):
        from decimal import Decimal

        from .services import RefundError, refund_order_payment

        transaccion = self._transaccion_aprobada()
        with self.assertRaises(RefundError):
            refund_order_payment(self.pedido, self.admin, amount=transaccion.amount + Decimal('1'))
        with self.assertRaises(RefundError):
            refund_order_payment(self.pedido, self.admin, amount=Decimal('0'))
        self.assertFalse(Refund.objects.exists())

    def test_proveedor_desconocido_no_revienta_sino_que_levanta_refund_error(self):
        from .services import RefundError, refund_order_payment

        PaymentTransaction.objects.create(
            order=self.pedido, provider='otro-proveedor', payment_id='x',
            external_reference=self.pedido.order_number,
            status=PaymentTransaction.Status.APPROVED, amount=self.pedido.total,
            idempotency_key='idem-refund-service-2',
        )
        with self.assertRaises(RefundError):
            refund_order_payment(self.pedido, self.admin)

class ConciliarReembolsoTests(TestCase):
    """Un reembolso pendiente se resuelve preguntando al proveedor."""

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        self.pedido = _crear_pedido()
        self.transaccion = PaymentTransaction.objects.create(
            order=self.pedido, provider='mock', payment_id='mock-pay-c',
            external_reference=self.pedido.order_number,
            status=PaymentTransaction.Status.APPROVED, amount=self.pedido.total,
            idempotency_key='idem-conciliar',
        )
        self.reembolso = Refund.objects.create(
            payment_transaction=self.transaccion, amount=self.transaccion.amount,
            status=Refund.Status.PENDING,
        )
        Refund.objects.filter(pk=self.reembolso.pk).update(created_at=timezone.now() - timedelta(minutes=30))
        self.reembolso.refresh_from_db()

    def _conciliar(self, registrados):
        from unittest.mock import patch

        from .services import conciliar_reembolso

        with patch('payments.providers.mock.MockPaymentProvider.list_refunds', return_value=registrados, create=True):
            return conciliar_reembolso(self.reembolso)

    def test_si_el_proveedor_lo_tiene_aprobado_queda_aprobado(self):
        resultado = self._conciliar([
            {'provider_refund_id': 'r-9', 'status': 'approved', 'amount': self.transaccion.amount},
        ])
        self.assertEqual(resultado.status, Refund.Status.APPROVED)
        self.assertEqual(resultado.provider_refund_id, 'r-9')

    def test_si_el_proveedor_no_lo_tiene_queda_fallido_y_se_puede_reintentar(self):
        from .services import refund_order_payment

        resultado = self._conciliar([])
        self.assertEqual(resultado.status, Refund.Status.FAILED)

        nuevo = refund_order_payment(self.pedido, None)
        self.assertEqual(nuevo.status, Refund.Status.APPROVED)

    def test_en_proceso_en_el_proveedor_sigue_pendiente_sin_tocarlo(self):
        Refund.objects.filter(pk=self.reembolso.pk).update(provider_refund_id='r-9')
        self.reembolso.refresh_from_db()

        resultado = self._conciliar([
            {'provider_refund_id': 'r-9', 'status': 'in_process', 'amount': self.transaccion.amount},
        ])

        self.assertEqual(resultado.status, Refund.Status.PENDING)
        self.assertEqual(resultado.error_message, '')

    def test_sin_id_un_reembolso_en_proceso_por_el_mismo_monto_sigue_pendiente(self):
        resultado = self._conciliar([
            {'provider_refund_id': 'r-9', 'status': 'in_process', 'amount': self.transaccion.amount},
        ])

        self.assertEqual(resultado.status, Refund.Status.PENDING)
        self.assertEqual(resultado.provider_refund_id, 'r-9')

    def test_con_id_se_empareja_por_el_id_y_no_por_el_monto(self):
        Refund.objects.filter(pk=self.reembolso.pk).update(provider_refund_id='r-1')
        self.reembolso.refresh_from_db()

        resultado = self._conciliar([
            {'provider_refund_id': 'r-otro', 'status': 'approved', 'amount': self.transaccion.amount},
            {'provider_refund_id': 'r-1', 'status': 'cancelled', 'amount': self.transaccion.amount},
        ])

        self.assertEqual(resultado.status, Refund.Status.FAILED)

    def test_con_id_ausente_de_la_lista_queda_fallido(self):
        Refund.objects.filter(pk=self.reembolso.pk).update(provider_refund_id='r-1')
        self.reembolso.refresh_from_db()

        resultado = self._conciliar([])

        self.assertEqual(resultado.status, Refund.Status.FAILED)

    def test_un_reembolso_del_proveedor_ya_reclamado_por_otro_registro_no_cuenta(self):
        Refund.objects.create(
            payment_transaction=self.transaccion, amount=self.transaccion.amount,
            status=Refund.Status.FAILED, provider_refund_id='r-9',
        )
        resultado = self._conciliar([
            {'provider_refund_id': 'r-9', 'status': 'approved', 'amount': self.transaccion.amount},
        ])
        self.assertEqual(resultado.status, Refund.Status.FAILED)

    def test_un_reembolso_reciente_no_se_concilia(self):
        from django.utils import timezone

        from .services import RefundError

        Refund.objects.filter(pk=self.reembolso.pk).update(created_at=timezone.now())
        self.reembolso.refresh_from_db()
        with self.assertRaises(RefundError):
            self._conciliar([])
        self.reembolso.refresh_from_db()
        self.assertEqual(self.reembolso.status, Refund.Status.PENDING)

    def test_si_el_proveedor_no_puede_consultarse_sigue_pendiente(self):
        from .services import RefundError, conciliar_reembolso

        with self.assertRaises(RefundError):
            conciliar_reembolso(self.reembolso)  # el mock no implementa list_refunds
        self.reembolso.refresh_from_db()
        self.assertEqual(self.reembolso.status, Refund.Status.PENDING)

    def test_el_comando_resuelve_los_pendientes(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        salida = StringIO()
        with patch('payments.providers.mock.MockPaymentProvider.list_refunds', return_value=[], create=True):
            call_command('conciliar_reembolsos', stdout=salida)

        self.reembolso.refresh_from_db()
        self.assertEqual(self.reembolso.status, Refund.Status.FAILED)
        self.assertIn(self.pedido.order_number, salida.getvalue())

