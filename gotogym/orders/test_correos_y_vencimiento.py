"""Correos del pedido, cupon devuelto al cancelar y vencimiento de pedidos sin pagar."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from payments.models import PaymentTransaction

from .models import Coupon, Order, OrderStatus, PaymentStatus
from .services import (
    apply_order_status_transition,
    cancel_expired_orders,
    confirm_payment,
    create_order_from_cart,
)
from .test_confirm_payment import DATOS, ConfirmPaymentBaseTestCase, _FakeTransaction


def _envejecer(pedido, horas):
    Order.objects.filter(pk=pedido.pk).update(created_at=timezone.now() - timedelta(hours=horas))


class CorreosDelPedidoTests(ConfirmPaymentBaseTestCase):
    def test_al_confirmarse_el_pago_llega_la_confirmacion(self):
        pedido = self._crear_pedido(2)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, [DATOS['email']])
        self.assertIn(pedido.order_number, correo.subject)
        self.assertIn('Producto confirm', correo.body)
        self.assertIn('Hola Ana', correo.body)
        self.assertIn('/pedidos-tienda/', correo.body)

    def test_un_aviso_repetido_no_envia_otra_confirmacion(self):
        pedido = self._crear_pedido(1)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
            confirm_payment(pedido, _FakeTransaction('approved'))
        self.assertEqual(len(mail.outbox), 1)

    def test_al_marcarse_enviado_llega_el_aviso_de_envio(self):
        pedido = self._crear_pedido(1)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            apply_order_status_transition(pedido, OrderStatus.SHIPPED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('va en camino', mail.outbox[0].subject)

    def test_un_pedido_pagado_que_se_cancela_promete_la_devolucion(self):
        pedido = self._crear_pedido(1)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('devolverte el dinero', mail.outbox[0].body)

    def test_sin_stock_al_aprobar_se_avisa_de_la_cancelacion(self):
        pedido = self._crear_pedido(5)
        self.variante.inventory.quantity_available = 0
        self.variante.inventory.save()
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('cancelado', mail.outbox[0].subject)

    def test_un_fallo_del_servidor_de_correo_no_rompe_la_confirmacion(self):
        from unittest.mock import patch

        pedido = self._crear_pedido(1)
        with patch('orders.correos.send_mail', side_effect=OSError('smtp caido')):
            with self.captureOnCommitCallbacks(execute=True):
                confirm_payment(pedido, _FakeTransaction('approved'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)


class CuponDevueltoTests(ConfirmPaymentBaseTestCase):
    def setUp(self):
        super().setUp()
        self.cupon = Coupon.objects.create(code='UNICO', value=Decimal('10'), max_uses=1)

    def _pedido_con_cupon(self):
        pedido = create_order_from_cart(
            self.usuario, {str(self.variante.pk): 1}, {**DATOS, 'coupon_code': 'UNICO'},
        )
        self.cupon.refresh_from_db()
        self.assertEqual(self.cupon.times_used, 1)
        return pedido

    def test_cancelar_el_pedido_devuelve_el_uso_del_cupon(self):
        pedido = self._pedido_con_cupon()
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        self.cupon.refresh_from_db()
        self.assertEqual(self.cupon.times_used, 0)
        self.assertTrue(self.cupon.is_usable())

    def test_un_pedido_confirmado_conserva_el_uso_del_cupon(self):
        pedido = self._pedido_con_cupon()
        confirm_payment(pedido, _FakeTransaction('approved'))
        self.cupon.refresh_from_db()
        self.assertEqual(self.cupon.times_used, 1)

    def test_sin_stock_al_aprobar_tambien_devuelve_el_cupon(self):
        pedido = create_order_from_cart(
            self.usuario, {str(self.variante.pk): 5}, {**DATOS, 'coupon_code': 'UNICO'},
        )
        self.variante.inventory.quantity_available = 0
        self.variante.inventory.save()
        confirm_payment(pedido, _FakeTransaction('approved'))
        self.cupon.refresh_from_db()
        self.assertEqual(self.cupon.times_used, 0)


class VencimientoDePedidosTests(ConfirmPaymentBaseTestCase):
    def test_cancela_el_pedido_sin_pagar_pasado_el_plazo(self):
        pedido = self._crear_pedido(1)
        _envejecer(pedido, 49)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(cancel_expired_orders(), 1)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
        self.assertEqual(pedido.payment_status, PaymentStatus.CANCELLED)
        self.assertIn('sin pago', pedido.internal_note)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('No se hizo ningún cobro', mail.outbox[0].body)

    def test_respeta_el_plazo(self):
        pedido = self._crear_pedido(1)
        _envejecer(pedido, 47)
        self.assertEqual(cancel_expired_orders(), 0)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.PENDING_PAYMENT)

    @override_settings(ORDER_PAYMENT_WINDOW_HOURS=1)
    def test_el_plazo_sale_de_la_configuracion(self):
        pedido = self._crear_pedido(1)
        _envejecer(pedido, 2)
        self.assertEqual(cancel_expired_orders(), 1)

    def test_devuelve_el_cupon(self):
        cupon = Coupon.objects.create(code='VENCE', value=Decimal('10'), max_uses=1)
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, {**DATOS, 'coupon_code': 'VENCE'})
        _envejecer(pedido, 72)
        cancel_expired_orders()
        cupon.refresh_from_db()
        self.assertEqual(cupon.times_used, 0)

    def test_no_toca_un_pedido_con_el_pago_en_verificacion(self):
        pedido = self._crear_pedido(1)
        PaymentTransaction.objects.create(
            order=pedido, provider='mercadopago', payment_id='123', external_reference=pedido.order_number,
            status=PaymentTransaction.Status.PENDING, amount=pedido.total, idempotency_key='k-verificacion',
        )
        _envejecer(pedido, 100)
        self.assertEqual(cancel_expired_orders(), 0)

    def test_cancela_si_el_intento_nunca_llego_al_proveedor(self):
        pedido = self._crear_pedido(1)
        PaymentTransaction.objects.create(
            order=pedido, provider='mercadopago', external_reference=pedido.order_number,
            status=PaymentTransaction.Status.PENDING, amount=pedido.total, idempotency_key='k-sin-pago',
        )
        _envejecer(pedido, 100)
        self.assertEqual(cancel_expired_orders(), 1)

    def test_no_toca_pedidos_ya_confirmados(self):
        pedido = self._crear_pedido(1)
        confirm_payment(pedido, _FakeTransaction('approved'))
        _envejecer(pedido, 100)
        self.assertEqual(cancel_expired_orders(), 0)

    def test_es_idempotente(self):
        pedido = self._crear_pedido(1)
        _envejecer(pedido, 100)
        self.assertEqual(cancel_expired_orders(), 1)
        self.assertEqual(cancel_expired_orders(), 0)

    def test_un_pago_que_llega_tarde_queda_marcado_para_reembolso(self):
        pedido = self._crear_pedido(1)
        _envejecer(pedido, 100)
        cancel_expired_orders()
        confirm_payment(pedido, _FakeTransaction('approved'))
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
        self.assertEqual(pedido.payment_status, PaymentStatus.APPROVED)
        self.assertIn('reembolso', pedido.internal_note)
        self.assertEqual(self._stock(), 5)

    def test_el_comando_informa_cuantos_cancelo(self):
        pedido = self._crear_pedido(1)
        _envejecer(pedido, 100)
        salida = StringIO()
        call_command('cancelar_pedidos_vencidos', stdout=salida)
        self.assertIn('Pedidos cancelados: 1', salida.getvalue())
