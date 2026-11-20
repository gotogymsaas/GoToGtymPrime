"""Panel de tarjetas de regalo: saldo por canjear, bloqueo, reenvio del
correo y que las compras de tarjetas no se cuenten como ventas."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from orders.models import GiftCard, GiftCardStatus
from orders.services import confirm_payment, create_gift_card_order

from . import metrics


class _Aprobada:
    status = 'approved'


class PanelDeTarjetasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            email='admin-tarjetas@example.com', username='admin-tarjetas@example.com', password='secret123',
        )
        cls.cliente = User.objects.create_user(
            email='cliente-tarjetas@example.com', username='cliente-tarjetas@example.com', password='secret123',
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.compra = create_gift_card_order(self.cliente, {
            'amount': Decimal('120000'), 'sender_name': 'Ana', 'recipient_name': 'Laura',
            'recipient_email': 'laura@example.com', 'message': '',
        })
        confirm_payment(self.compra, _Aprobada())
        self.tarjeta = GiftCard.objects.get(purchase_order=self.compra)
        mail.outbox.clear()

    def test_la_lista_muestra_el_saldo_por_canjear(self):
        respuesta = self.client.get(reverse('admin_gift_cards'))
        self.assertContains(respuesta, '$120.000')
        self.assertContains(respuesta, self.tarjeta.masked_code)
        self.assertNotContains(respuesta, self.tarjeta.display_code)

    def test_se_busca_por_los_ultimos_cuatro_del_codigo(self):
        respuesta = self.client.get(reverse('admin_gift_cards'), {'q': self.tarjeta.code[-4:]})
        self.assertContains(respuesta, 'laura@example.com')

    def test_bloquear_y_desbloquear(self):
        url = reverse('admin_gift_card_toggle', args=[self.tarjeta.pk])
        self.client.post(url, {'reason': 'Reclamo en curso'})
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.status, GiftCardStatus.DISABLED)
        self.assertEqual(self.tarjeta.disabled_reason, 'Reclamo en curso')
        self.client.post(url)
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.status, GiftCardStatus.ACTIVE)

    def test_reenviar_a_un_correo_corregido(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('admin_gift_card_resend', args=[self.tarjeta.pk]), {'recipient_email': 'laura.b@example.com'},
            )
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.recipient_email, 'laura.b@example.com')
        self.assertEqual(mail.outbox[-1].to, ['laura.b@example.com'])

    def test_un_cliente_no_entra_al_panel_de_tarjetas(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('admin_gift_cards'))
        self.assertNotEqual(respuesta.status_code, 200)

    def test_la_compra_de_tarjetas_no_cuenta_como_venta(self):
        hoy = timezone.localdate()
        resumen = metrics.resumen_ventas(hoy - timedelta(days=1), hoy)
        self.assertEqual(resumen['pedidos'], 0)
        filas = list(metrics.filas_exportacion(hoy - timedelta(days=1), hoy))
        self.assertEqual(filas[0]['tipo'], 'gift_card')
        self.assertEqual(filas[0]['venta_valida'], 'no')

    def test_el_detalle_del_pedido_ofrece_el_retracto_mientras_no_se_use(self):
        respuesta = self.client.get(reverse('admin_order_detail', args=[self.compra.order_number]))
        self.assertContains(respuesta, 'Tarjeta de regalo comprada')
        self.assertContains(respuesta, 'Retracto')
        self.assertContains(respuesta, 'value="cancelled"')


class InterruptorModoDePruebasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            email='admin-modo@example.com', username='admin-modo@example.com', password='secret123',
        )

    def test_el_interruptor_enciende_y_apaga_el_modo_y_avisa_en_el_panel(self):
        from .models import PanelSettings

        self.client.force_login(self.admin)
        url = reverse('admin_staff_checkout_without_payment_toggle')
        self.client.post(url, {'activar': '1'})
        self.assertTrue(PanelSettings.load().staff_checkout_without_payment)
        self.assertContains(self.client.get(reverse('admin_dashboard')), 'Modo de pruebas encendido')
        self.client.post(url, {'activar': '0'})
        self.assertFalse(PanelSettings.load().staff_checkout_without_payment)

    def test_los_pedidos_de_prueba_no_cuentan_como_venta(self):
        from orders.models import Order

        cliente = get_user_model().objects.create_user(
            email='c-modo@example.com', username='c-modo@example.com', password='x',
        )
        compra = create_gift_card_order(cliente, {
            'amount': Decimal('80000'), 'sender_name': 'Ana', 'recipient_name': 'Laura',
            'recipient_email': 'laura@example.com', 'message': '',
        })
        Order.objects.filter(pk=compra.pk).update(kind='products', is_test_order=True, payment_status='approved')
        hoy = timezone.localdate()
        self.assertEqual(metrics.resumen_ventas(hoy - timedelta(days=1), hoy)['pedidos'], 0)
        fila, = metrics.filas_exportacion(hoy - timedelta(days=1), hoy)
        self.assertEqual(fila['prueba_sin_pago'], 'si')
        self.assertEqual(fila['venta_valida'], 'no')
