"""Interruptor "Recibir pagos": con los pagos deshabilitados el checkout no abre
intentos nuevos, y volver a habilitarlos deja todo como estaba."""
from decimal import Decimal

from administracion.models import PanelSettings
from administracion.test_admin_panel import PanelAdminBaseTestCase
from django.urls import reverse
from orders.models import Order, OrderStatus, PaymentStatus
from payments.models import PaymentTransaction


class RecibirPagosTests(PanelAdminBaseTestCase):
    def _alternar(self, valor):
        return self.client.post(reverse('admin_online_payments_toggle'), {'habilitar': valor})

    def _pedido(self):
        return Order.objects.create(
            order_number='GTG-PAGOS-0001', user=self.cliente, email='cliente-panel@example.com',
            phone='3000000000', subtotal=Decimal('50000'), total=Decimal('50000'),
            order_status=OrderStatus.PENDING_PAYMENT, payment_status=PaymentStatus.PENDING,
        )

    def test_por_defecto_se_reciben_pagos(self):
        self.assertTrue(PanelSettings.pagos_habilitados())

    def test_deshabilitar_y_habilitar(self):
        self._alternar('0')
        self.assertFalse(PanelSettings.pagos_habilitados())
        self._alternar('1')
        self.assertTrue(PanelSettings.pagos_habilitados())

    def test_el_panel_muestra_el_interruptor_con_su_confirmacion(self):
        respuesta = self.client.get(reverse('admin_dashboard'))
        self.assertContains(respuesta, 'Recibir pagos')
        self.assertContains(respuesta, '¿Dejar de recibir pagos?')
        self._alternar('0')
        respuesta = self.client.get(reverse('admin_dashboard'))
        self.assertContains(respuesta, '¿Volver a recibir pagos?')
        self.assertContains(respuesta, 'Los pagos en línea están deshabilitados')

    def test_cliente_no_puede_cambiarlo(self):
        self.client.force_login(self.cliente)
        self._alternar('0')
        self.assertTrue(PanelSettings.pagos_habilitados())

    def test_deshabilitados_no_se_abre_un_pago_nuevo(self):
        pedido = self._pedido()
        self._alternar('0')
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('payments:pending', args=[pedido.order_number]))
        self.assertRedirects(respuesta, reverse('orders:order_detail', args=[pedido.order_number]))
        self.assertFalse(PaymentTransaction.objects.exists())

    def test_habilitados_el_pago_se_abre(self):
        pedido = self._pedido()
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('payments:pending', args=[pedido.order_number]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(PaymentTransaction.objects.filter(order=pedido).exists())

    def test_el_pedido_pendiente_no_ofrece_ir_a_pagar_si_estan_deshabilitados(self):
        pedido = self._pedido()
        self._alternar('0')
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('orders:order_detail', args=[pedido.order_number]))
        self.assertNotContains(respuesta, reverse('payments:pending', args=[pedido.order_number]))
        self.assertContains(respuesta, 'deshabilitados temporalmente')
