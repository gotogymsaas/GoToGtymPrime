"""Historial de estados, hitos del pedido y restricciones del esquema."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Coupon, Order, OrderItem, OrderStatus, OrderStatusHistory
from .services import apply_order_status_transition, cancel_expired_orders, confirm_payment
from .test_confirm_payment import ConfirmPaymentBaseTestCase, _FakeTransaction


class HistorialDeEstadosTests(ConfirmPaymentBaseTestCase):
    def _recorrido(self, pedido):
        return list(pedido.status_history.values_list('from_status', 'to_status'))

    def test_el_pedido_nuevo_queda_registrado(self):
        pedido = self._crear_pedido(1)
        self.assertEqual(self._recorrido(pedido), [('', OrderStatus.PENDING_PAYMENT)])

    def test_confirmar_el_pago_registra_el_cambio_y_fija_paid_at(self):
        pedido = self._crear_pedido(1)
        confirm_payment(pedido, _FakeTransaction('approved'))
        pedido.refresh_from_db()
        self.assertIsNotNone(pedido.paid_at)
        self.assertEqual(self._recorrido(pedido)[-1], (OrderStatus.PENDING_PAYMENT, OrderStatus.CONFIRMED))

    def test_cada_transicion_registra_quien_la_hizo(self):
        pedido = self._crear_pedido(1)
        confirm_payment(pedido, _FakeTransaction('approved'))
        apply_order_status_transition(pedido, OrderStatus.PREPARING, changed_by=self.usuario)
        registro = pedido.status_history.latest('id')
        self.assertEqual(registro.changed_by, self.usuario)
        self.assertEqual((registro.from_status, registro.to_status), (OrderStatus.CONFIRMED, OrderStatus.PREPARING))

    def test_envio_y_cancelacion_fijan_sus_hitos(self):
        pedido = self._crear_pedido(1)
        confirm_payment(pedido, _FakeTransaction('approved'))
        apply_order_status_transition(pedido, OrderStatus.SHIPPED)
        pedido.refresh_from_db()
        self.assertIsNotNone(pedido.shipped_at)
        self.assertIsNone(pedido.cancelled_at)

        otro = self._crear_pedido(1)
        apply_order_status_transition(otro, OrderStatus.CANCELLED)
        otro.refresh_from_db()
        self.assertIsNotNone(otro.cancelled_at)

    def test_el_estado_del_envio_sigue_al_del_pedido(self):
        pedido = self._crear_pedido(1)
        confirm_payment(pedido, _FakeTransaction('approved'))
        apply_order_status_transition(pedido, OrderStatus.SHIPPED)
        pedido.shipping_quote.refresh_from_db()
        self.assertEqual(pedido.shipping_quote.shipping_status, 'shipped')
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        pedido.shipping_quote.refresh_from_db()
        self.assertEqual(pedido.shipping_quote.shipping_status, 'delivered')

    def test_la_cancelacion_por_vencimiento_queda_con_nota(self):
        pedido = self._crear_pedido(1)
        Order.objects.filter(pk=pedido.pk).update(created_at=pedido.created_at.replace(year=2020))
        cancel_expired_orders()
        registro = pedido.status_history.latest('id')
        self.assertEqual(registro.to_status, OrderStatus.CANCELLED)
        self.assertIn('Sin pago', registro.note)
        pedido.refresh_from_db()
        self.assertIsNotNone(pedido.cancelled_at)


class RestriccionesDelEsquemaTests(ConfirmPaymentBaseTestCase):
    def test_no_se_acepta_una_linea_con_cantidad_cero(self):
        pedido = self._crear_pedido(1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=pedido, variant=self.variante, product_name_snapshot='x', sku_snapshot='x',
                size_snapshot='S', color_snapshot='negro', unit_price_snapshot=Decimal('1.00'),
                quantity=0, line_total=Decimal('0.00'),
            )

    def test_no_se_acepta_un_total_negativo(self):
        pedido = self._crear_pedido(1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=pedido.pk).update(total=Decimal('-1.00'))

    def test_un_porcentaje_de_cupon_no_puede_pasar_de_100(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Coupon.objects.create(code='MUCHO', discount_type='percentage', value=Decimal('150.00'))

    def test_un_valor_fijo_puede_pasar_de_100(self):
        Coupon.objects.create(code='FIJO', discount_type='fixed', value=Decimal('150000.00'))


class CodigoDeCuponTests(TestCase):
    def test_el_codigo_se_guarda_en_mayusculas(self):
        cupon = Coupon.objects.create(code=' verano10 ', value=Decimal('10.00'))
        self.assertEqual(cupon.code, 'VERANO10')
