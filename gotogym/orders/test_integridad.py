"""Cupo de cupones y transiciones de estado ante lecturas desactualizadas."""
from decimal import Decimal
from unittest.mock import patch

from .models import Coupon, Order, OrderStatus
from .services import (
    CheckoutError,
    InvalidOrderTransitionError,
    apply_order_status_transition,
    confirm_payment,
    create_order_from_cart,
)
from .test_confirm_payment import DATOS, ConfirmPaymentBaseTestCase, _FakeTransaction


class CupoDelCuponTests(ConfirmPaymentBaseTestCase):
    def _comprar(self, codigo):
        return create_order_from_cart(
            self.usuario, {str(self.variante.pk): 1}, {**DATOS, 'coupon_code': codigo},
        )

    def test_un_cupon_agotado_entre_la_lectura_y_la_escritura_rechaza_el_pedido(self):
        # `get_usable_coupon` leyo el cupon con un uso libre; otra compra tomo
        # ese uso antes de que esta escriba.
        cupon = Coupon.objects.create(code='ULTIMO', value=Decimal('10'), max_uses=1)
        leido_con_cupo = Coupon.objects.get(pk=cupon.pk)
        Coupon.objects.filter(pk=cupon.pk).update(times_used=1)

        with patch('orders.services.get_usable_coupon', return_value=leido_con_cupo):
            with self.assertRaises(CheckoutError):
                self._comprar('ULTIMO')

        cupon.refresh_from_db()
        self.assertEqual(cupon.times_used, 1)
        self.assertFalse(Order.objects.filter(coupon=cupon).exists())

    def test_el_ultimo_uso_se_concede_una_sola_vez(self):
        cupon = Coupon.objects.create(code='UNICO2', value=Decimal('10'), max_uses=1)

        self._comprar('UNICO2')

        cupon.refresh_from_db()
        self.assertEqual(cupon.times_used, 1)

    def test_un_cupon_sin_tope_cuenta_todos_los_usos(self):
        cupon = Coupon.objects.create(code='LIBRE', value=Decimal('10'))

        self._comprar('LIBRE')
        self._comprar('LIBRE')

        cupon.refresh_from_db()
        self.assertEqual(cupon.times_used, 2)


class TransicionConLecturaVencidaTests(ConfirmPaymentBaseTestCase):
    def test_cancelar_con_una_instancia_vieja_valida_contra_el_estado_real(self):
        pedido = self._crear_pedido(1)
        vieja = Order.objects.get(pk=pedido.pk)  # leida mientras estaba pendiente de pago
        confirm_payment(pedido, _FakeTransaction('approved'))

        # La instancia vieja aun dice `pending_payment`; el pedido ya esta
        # confirmado y su stock descontado.
        self.assertEqual(vieja.order_status, OrderStatus.PENDING_PAYMENT)
        apply_order_status_transition(vieja, OrderStatus.CANCELLED)

        self.assertEqual(self._stock(), 5)

    def test_una_transicion_que_ya_no_es_valida_se_rechaza(self):
        pedido = self._crear_pedido(1)
        vieja = Order.objects.get(pk=pedido.pk)
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)

        with self.assertRaises(InvalidOrderTransitionError):
            apply_order_status_transition(vieja, OrderStatus.CANCELLED)
