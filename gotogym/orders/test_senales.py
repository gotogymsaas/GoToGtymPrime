"""Las senales del ciclo de vida del pedido se emiten en el punto donde cambia
el pedido, con el pedido como argumento, y un receptor que falla deshace el
cambio."""
from unittest.mock import Mock

from .models import Order, OrderStatus
from .senales import pedido_anulado, pedido_cobrado, pedido_entregado
from .services import apply_order_status_transition, confirm_payment, registrar_pago_revertido
from .test_confirm_payment import ConfirmPaymentBaseTestCase, _FakeTransaction


class SenalesDelPedidoTests(ConfirmPaymentBaseTestCase):
    def setUp(self):
        super().setUp()
        self.cobrado, self.entregado, self.anulado = Mock(), Mock(), Mock()
        for senal, receptor in (
            (pedido_cobrado, self.cobrado), (pedido_entregado, self.entregado), (pedido_anulado, self.anulado),
        ):
            senal.connect(receptor, weak=False, dispatch_uid=f'prueba-{id(senal)}')
            self.addCleanup(senal.disconnect, dispatch_uid=f'prueba-{id(senal)}')

    def _confirmado(self):
        pedido = self._crear_pedido(1)
        confirm_payment(pedido, _FakeTransaction('approved'))
        return pedido

    def test_confirmar_el_pago_emite_cobrado_una_vez_con_el_pedido(self):
        pedido = self._confirmado()

        self.cobrado.assert_called_once()
        kwargs = self.cobrado.call_args.kwargs
        self.assertIs(kwargs['sender'], Order)
        self.assertEqual(kwargs['order'].pk, pedido.pk)
        self.entregado.assert_not_called()
        self.anulado.assert_not_called()

    def test_una_confirmacion_repetida_no_vuelve_a_emitir(self):
        pedido = self._confirmado()
        confirm_payment(pedido, _FakeTransaction('approved'))
        self.cobrado.assert_called_once()

    def test_un_pedido_de_prueba_no_emite_cobrado(self):
        pedido = self._crear_pedido(1)
        Order.objects.filter(pk=pedido.pk).update(is_test_order=True)
        pedido.refresh_from_db()

        confirm_payment(pedido, _FakeTransaction('approved'))

        self.cobrado.assert_not_called()

    def test_un_pedido_cancelado_al_confirmar_por_falta_de_stock_no_emite_cobrado(self):
        pedido = self._crear_pedido(1)
        self.variante.inventory.quantity_available = 0
        self.variante.inventory.save(update_fields=['quantity_available'])

        confirm_payment(pedido, _FakeTransaction('approved'))

        self.cobrado.assert_not_called()
        self.anulado.assert_not_called()

    def test_entregar_emite_entregado(self):
        pedido = self._confirmado()

        apply_order_status_transition(pedido, OrderStatus.DELIVERED)

        self.entregado.assert_called_once()
        self.assertEqual(self.entregado.call_args.kwargs['order'].pk, pedido.pk)
        self.anulado.assert_not_called()

    def test_cancelar_y_devolver_emiten_anulado_sin_motivo(self):
        cancelado = self._confirmado()
        apply_order_status_transition(cancelado, OrderStatus.CANCELLED)
        devuelto = self._confirmado()
        apply_order_status_transition(devuelto, OrderStatus.SHIPPED)
        apply_order_status_transition(devuelto, OrderStatus.RETURNED)

        self.assertEqual(self.anulado.call_count, 2)
        for llamada in self.anulado.call_args_list:
            self.assertNotIn('motivo', llamada.kwargs)
        self.assertEqual(
            [llamada.kwargs['order'].pk for llamada in self.anulado.call_args_list], [cancelado.pk, devuelto.pk],
        )
        self.entregado.assert_not_called()

    def test_un_pago_revertido_por_el_proveedor_emite_anulado_con_el_motivo(self):
        pedido = self._confirmado()

        with self.assertLogs('orders.services', level='ERROR'):
            registrar_pago_revertido(pedido, 'Contracargo.')

        self.anulado.assert_called_once()
        self.assertEqual(self.anulado.call_args.kwargs['motivo'], 'Contracargo.')
        self.assertEqual(self.anulado.call_args.kwargs['order'].pk, pedido.pk)

    def test_un_receptor_que_falla_deshace_la_transicion(self):
        pedido = self._confirmado()
        self.entregado.side_effect = RuntimeError('fallo del receptor')

        with self.assertRaises(RuntimeError):
            apply_order_status_transition(pedido, OrderStatus.DELIVERED)

        self.assertEqual(Order.objects.get(pk=pedido.pk).order_status, OrderStatus.CONFIRMED)
