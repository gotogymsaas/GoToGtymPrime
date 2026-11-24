"""Los receptores del programa de afiliados quedan conectados a las senales de
`orders` al arrancar la app."""
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from orders.models import Order
from orders.senales import pedido_anulado, pedido_cobrado, pedido_entregado

from . import receptores


class ConexionDeReceptoresTests(SimpleTestCase):
    def test_cada_senal_tiene_su_receptor_conectado(self):
        orden = Order(pk=1)
        for senal, destino in (
            (pedido_cobrado, 'register_order_commission'),
            (pedido_entregado, 'schedule_order_commission_validation'),
            (pedido_anulado, 'revert_order_commission'),
        ):
            with patch.object(receptores, destino) as servicio:
                senal.send(sender=Order, order=orden)
            servicio.assert_called_once_with(orden)

    def test_anular_con_motivo_lo_pasa_y_sin_motivo_usa_el_de_la_funcion(self):
        orden = Mock()
        with patch.object(receptores, 'revert_order_commission') as servicio:
            pedido_anulado.send(sender=Order, order=orden, motivo='Contracargo.')
            servicio.assert_called_once_with(orden, 'Contracargo.')
            servicio.reset_mock()
            pedido_anulado.send(sender=Order, order=orden)
            servicio.assert_called_once_with(orden)
