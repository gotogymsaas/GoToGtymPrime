"""Modo de pruebas del panel: las cuentas del equipo confirman sin pagar; los
clientes siguen pagando. Los pedidos quedan marcados como prueba."""
from decimal import Decimal
from unittest.mock import patch

from carrito.services import write_cart
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from . import facturacion
from .models import GiftCard, GiftCardStatus, OrderKind, OrderStatus, PaymentStatus
from .services import create_order_from_cart
from .test_confirm_payment import DATOS, ConfirmPaymentBaseTestCase


def _modo_de_pruebas(activo):
    PanelSettings = apps.get_model('administracion', 'PanelSettings')
    PanelSettings.objects.update_or_create(pk=1, defaults={'staff_checkout_without_payment': activo})


class ModoSinPagoTests(ConfirmPaymentBaseTestCase):
    def setUp(self):
        super().setUp()
        self.staff = get_user_model().objects.create_user(
            email='equipo-pruebas@example.com', username='equipo-pruebas@example.com',
            password='secret123', is_staff=True,
        )

    def _checkout(self, usuario):
        self.client.force_login(usuario)
        sesion = self.client.session
        write_cart(sesion, {str(self.variante.pk): 1})
        sesion.save()
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('orders:checkout'), DATOS)
        return respuesta, usuario.orders.get(kind=OrderKind.PRODUCTS)

    def test_el_equipo_confirma_sin_pagar_y_queda_como_prueba(self):
        _modo_de_pruebas(True)
        with patch('orders.services.register_order_commission') as comision:
            respuesta, pedido = self._checkout(self.staff)
        self.assertRedirects(respuesta, reverse('orders:order_detail', args=[pedido.order_number]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(pedido.payment_status, PaymentStatus.APPROVED)
        self.assertTrue(pedido.is_test_order)
        self.assertEqual(pedido.payment_transactions.count(), 0)
        self.assertIn('equipo-pruebas@example.com', pedido.internal_note)
        self.assertEqual(self._stock(), 4)
        self.assertFalse(facturacion.facturable(pedido))
        comision.assert_not_called()
        self.assertContains(self.client.get(respuesta.url), 'Pedido de prueba')

    def test_un_cliente_paga_aunque_el_modo_este_encendido(self):
        _modo_de_pruebas(True)
        respuesta, pedido = self._checkout(self.usuario)
        self.assertRedirects(
            respuesta, reverse('payments:pending', args=[pedido.order_number]), fetch_redirect_response=False,
        )
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.PENDING_PAYMENT)
        self.assertFalse(pedido.is_test_order)

    def test_con_el_modo_apagado_el_equipo_paga_normal(self):
        _modo_de_pruebas(False)
        respuesta, pedido = self._checkout(self.staff)
        self.assertRedirects(
            respuesta, reverse('payments:pending', args=[pedido.order_number]), fetch_redirect_response=False,
        )
        self.assertFalse(pedido.is_test_order)

    def test_un_pedido_pendiente_se_confirma_al_ir_a_pagar(self):
        pedido = create_order_from_cart(self.staff, {str(self.variante.pk): 1}, DATOS)
        _modo_de_pruebas(True)
        self.client.force_login(self.staff)
        respuesta = self.client.get(reverse('payments:pending', args=[pedido.order_number]))
        self.assertRedirects(respuesta, reverse('orders:order_detail', args=[pedido.order_number]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)
        self.assertTrue(pedido.is_test_order)

    def test_la_tarjeta_de_regalo_se_activa_y_se_envia_sin_pagar(self):
        _modo_de_pruebas(True)
        self.client.force_login(self.staff)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('tarjeta_regalo'), {
                'amount': '100000', 'sender_name': 'Equipo', 'recipient_name': 'Laura',
                'recipient_email': 'laura@example.com', 'recipient_email_confirm': 'laura@example.com',
                'message': 'Prueba', 'accept_conditions': 'on',
            })
        tarjeta = GiftCard.objects.get(buyer=self.staff)
        self.assertEqual(tarjeta.status, GiftCardStatus.ACTIVE)
        self.assertTrue(tarjeta.purchase_order.is_test_order)
        destinatarios = [correo.to for correo in mail.outbox]
        self.assertIn(['laura@example.com'], destinatarios)
        self.assertEqual(tarjeta.initial_amount, Decimal('100000'))
