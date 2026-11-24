"""La comision del afiliado sigue el ciclo del pedido: se registra al cobrarse,
empieza su validacion al entregarse y se revierte al cancelarse, devolverse o
revertirse el pago.

Fijan lo observable desde fuera (que se registra, en que orden respecto a lo
demas y que pasa si algo falla), sin depender de que modulo llame a cual.
"""
from unittest.mock import patch

from django.db.models.signals import post_save
from django.test import override_settings
from orders.models import Order, OrderStatus, PaymentStatus
from orders.services import (
    apply_order_status_transition,
    confirm_payment,
    registrar_pago_revertido,
)

from .models import Commission, CommissionStatus
from .tests import AfiliadoTestBase, _FakeTransaction

EVENTOS: list[str] = []


class _RegistroDeTareas:
    """Backend de tareas que anota cada tarea en el momento de encolarla."""

    dentro_de_la_transaccion = True

    def enqueue(self, ruta, args, kwargs):
        EVENTOS.append(ruta)


def _anotar_comision(sender, **kwargs):
    EVENTOS.append('comision')


@override_settings(TASK_BACKEND='afiliados.test_comision_y_pedidos._RegistroDeTareas')
class ComisionSegunElCicloDelPedidoTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        EVENTOS.clear()
        post_save.connect(_anotar_comision, sender=Commission, dispatch_uid='test_comision_y_pedidos')
        self.addCleanup(post_save.disconnect, sender=Commission, dispatch_uid='test_comision_y_pedidos')
        self.addCleanup(EVENTOS.clear)

    def _pedido_pendiente(self):
        pedido = self._crear_pedido_referido(self.perfil)
        EVENTOS.clear()
        return pedido

    def test_al_confirmar_el_pago_la_comision_se_registra_antes_que_la_factura_y_el_correo(self):
        pedido = self._pedido_pendiente()

        confirm_payment(pedido, _FakeTransaction('approved'))

        self.assertEqual(Commission.objects.filter(order=pedido).count(), 1)
        self.assertEqual(
            EVENTOS,
            ['comision', 'orders.facturacion.emitir_factura', 'orders.correos.pedido_confirmado'],
        )

    def test_un_pedido_de_prueba_no_genera_comision_ni_factura(self):
        pedido = self._pedido_pendiente()
        Order.objects.filter(pk=pedido.pk).update(is_test_order=True)
        pedido.refresh_from_db()

        confirm_payment(pedido, _FakeTransaction('approved'))

        self.assertFalse(Commission.objects.filter(order=pedido).exists())
        self.assertEqual(EVENTOS, ['orders.correos.pedido_confirmado'])

    def test_un_pedido_sin_cupon_de_afiliado_no_genera_comision(self):
        pedido = self._pedido_pendiente()
        Order.objects.filter(pk=pedido.pk).update(referred_by=None)
        pedido.refresh_from_db()

        confirm_payment(pedido, _FakeTransaction('approved'))

        self.assertFalse(Commission.objects.filter(order=pedido).exists())

    def test_una_confirmacion_repetida_no_duplica_la_comision(self):
        pedido = self._pedido_pendiente()
        confirm_payment(pedido, _FakeTransaction('approved'))
        confirm_payment(pedido, _FakeTransaction('approved'))
        self.assertEqual(Commission.objects.filter(order=pedido).count(), 1)

    def test_un_pedido_cancelado_por_falta_de_stock_al_confirmar_no_genera_comision(self):
        pedido = self._pedido_pendiente()
        self.variante.inventory.quantity_available = 0
        self.variante.inventory.save(update_fields=['quantity_available'])

        confirm_payment(pedido, _FakeTransaction('approved'))

        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
        self.assertFalse(Commission.objects.filter(order=pedido).exists())

    def test_si_registrar_la_comision_falla_el_pago_no_queda_confirmado(self):
        pedido = self._pedido_pendiente()

        with patch.object(Commission, 'save', side_effect=RuntimeError('sin base')):
            with self.assertRaises(RuntimeError):
                confirm_payment(pedido, _FakeTransaction('approved'))

        pedido = Order.objects.get(pk=pedido.pk)
        self.assertEqual(pedido.order_status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(pedido.payment_status, PaymentStatus.PENDING)
        self.assertEqual(EVENTOS, [])

    def test_al_entregarse_empieza_la_validacion_de_la_comision(self):
        pedido = self._pedido_pendiente()
        confirm_payment(pedido, _FakeTransaction('approved'))
        comision = Commission.objects.get(order=pedido)
        self.assertIsNone(comision.validation_ends_at)

        apply_order_status_transition(pedido, OrderStatus.DELIVERED)

        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.PENDING)
        self.assertIsNotNone(comision.validation_ends_at)

    def test_entregar_un_pedido_sin_comision_no_hace_nada(self):
        pedido = self._pedido_pendiente()
        Order.objects.filter(pk=pedido.pk).update(referred_by=None)
        pedido.refresh_from_db()
        confirm_payment(pedido, _FakeTransaction('approved'))

        apply_order_status_transition(pedido, OrderStatus.DELIVERED)

        self.assertFalse(Commission.objects.filter(order=pedido).exists())

    def test_si_fijar_la_validacion_falla_la_entrega_no_queda_registrada(self):
        pedido = self._pedido_pendiente()
        confirm_payment(pedido, _FakeTransaction('approved'))

        with patch.object(Commission, 'save', side_effect=RuntimeError('sin base')):
            with self.assertRaises(RuntimeError):
                apply_order_status_transition(pedido, OrderStatus.DELIVERED)

        self.assertEqual(Order.objects.get(pk=pedido.pk).order_status, OrderStatus.CONFIRMED)

    def test_cancelar_revierte_la_comision_con_el_motivo_por_defecto_y_antes_del_correo(self):
        pedido = self._pedido_pendiente()
        confirm_payment(pedido, _FakeTransaction('approved'))
        EVENTOS.clear()

        apply_order_status_transition(pedido, OrderStatus.CANCELLED)

        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.status, CommissionStatus.REVERTED)
        self.assertEqual(comision.adjustment_reason, 'El pedido se canceló, devolvió o reembolso.')
        self.assertEqual(EVENTOS, ['comision', 'orders.correos.pedido_cancelado'])

    def test_devolver_revierte_la_comision(self):
        pedido = self._pedido_pendiente()
        confirm_payment(pedido, _FakeTransaction('approved'))
        apply_order_status_transition(pedido, OrderStatus.SHIPPED)

        apply_order_status_transition(pedido, OrderStatus.RETURNED)

        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.REVERTED)

    def test_si_revertir_la_comision_falla_la_cancelacion_no_queda_registrada(self):
        pedido = self._pedido_pendiente()
        confirm_payment(pedido, _FakeTransaction('approved'))

        with patch.object(Commission, 'save', side_effect=RuntimeError('sin base')):
            with self.assertRaises(RuntimeError):
                apply_order_status_transition(pedido, OrderStatus.CANCELLED)

        self.assertEqual(Order.objects.get(pk=pedido.pk).order_status, OrderStatus.CONFIRMED)

    def test_un_pago_revertido_por_el_proveedor_anula_la_comision_con_el_motivo_dado(self):
        pedido = self._pedido_pendiente()
        confirm_payment(pedido, _FakeTransaction('approved'))

        with self.assertLogs('orders.services', level='ERROR'):
            registrar_pago_revertido(pedido, 'Contracargo del proveedor.')

        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.status, CommissionStatus.REVERTED)
        self.assertEqual(comision.adjustment_reason, 'Contracargo del proveedor.')
