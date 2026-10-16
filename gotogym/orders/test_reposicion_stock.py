"""El stock descontado al confirmar el pago se devuelve al cancelar o devolver."""
from inventory.models import InventoryAdjustment, InventoryAdjustmentReason

from .models import OrderStatus
from .services import apply_order_status_transition, confirm_payment
from .test_confirm_payment import ConfirmPaymentBaseTestCase, _FakeTransaction


class ReposicionDeStockTests(ConfirmPaymentBaseTestCase):
    def _pedido_confirmado(self, cantidad=2):
        pedido = self._crear_pedido(cantidad)
        confirm_payment(pedido, _FakeTransaction('approved'))
        pedido.refresh_from_db()
        self.assertEqual(self._stock(), 5 - cantidad)
        return pedido

    def test_cancelar_un_pedido_confirmado_devuelve_el_stock(self):
        pedido = self._pedido_confirmado(2)
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        self.assertEqual(self._stock(), 5)

    def test_cancelar_un_pedido_en_preparacion_devuelve_el_stock(self):
        pedido = self._pedido_confirmado(3)
        apply_order_status_transition(pedido, OrderStatus.PREPARING)
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        self.assertEqual(self._stock(), 5)

    def test_devolver_un_pedido_entregado_devuelve_el_stock(self):
        pedido = self._pedido_confirmado(2)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        apply_order_status_transition(pedido, OrderStatus.RETURNED)
        self.assertEqual(self._stock(), 5)

    def test_cancelar_un_pedido_sin_pago_no_toca_el_stock(self):
        pedido = self._crear_pedido(2)
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        self.assertEqual(self._stock(), 5)
        self.assertFalse(
            InventoryAdjustment.objects.filter(reason=InventoryAdjustmentReason.RESTOCK).exists(),
        )

    def test_la_reposicion_queda_en_el_kardex(self):
        pedido = self._pedido_confirmado(2)
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        ajuste = InventoryAdjustment.objects.get(reason=InventoryAdjustmentReason.RESTOCK)
        self.assertEqual(ajuste.delta, 2)
        self.assertEqual(ajuste.quantity_after, 5)

    def test_una_variante_borrada_no_impide_cancelar(self):
        pedido = self._pedido_confirmado(2)
        pedido.items.update(variant=None)
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
