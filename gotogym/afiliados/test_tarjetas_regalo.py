"""Comision de afiliados y tarjetas de regalo: comprar una tarjeta no genera
comision; canjearla en un pedido con codigo de afiliado si, sobre el
subtotal, como cualquier venta."""
from decimal import Decimal

from orders.models import GiftCard
from orders.services import confirm_payment, create_gift_card_order, create_order_from_cart

from .models import Commission
from .tests import DATOS_ENTREGA, AfiliadoTestBase, _FakeTransaction


class ComisionConTarjetaDeRegaloTests(AfiliadoTestBase):
    def _tarjeta_activa(self, valor):
        compra = create_gift_card_order(self.comprador, {
            'amount': valor, 'sender_name': 'Ana', 'recipient_name': 'Laura',
            'recipient_email': 'laura@example.com', 'message': '',
        })
        confirm_payment(compra, _FakeTransaction('approved'))
        return compra, GiftCard.objects.get(purchase_order=compra)

    def test_comprar_una_tarjeta_no_genera_comision(self):
        self._crear_perfil_aprobado()
        compra, _tarjeta = self._tarjeta_activa(Decimal('200000'))
        self.assertIsNone(compra.referred_by)
        self.assertFalse(Commission.objects.filter(order=compra).exists())

    def test_canjear_una_tarjeta_con_codigo_de_afiliado_genera_comision_sobre_el_subtotal(self):
        perfil = self._crear_perfil_aprobado()
        _compra, tarjeta = self._tarjeta_activa(Decimal('500000'))
        entrega = dict(DATOS_ENTREGA, coupon_code=perfil.coupons.first().code, gift_card_code=tarjeta.code)
        pedido = create_order_from_cart(self.comprador, {str(self.variante.pk): 1}, entrega)
        pedido.refresh_from_db()
        # La tarjeta cubrio todo: el pedido se confirmo sin pasar por la pasarela.
        self.assertEqual(pedido.total, 0)
        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.afiliado, perfil)
        self.assertEqual(comision.base_amount, pedido.subtotal)
