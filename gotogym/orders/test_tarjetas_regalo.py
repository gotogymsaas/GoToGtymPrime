"""Tarjetas de regalo: compra, activacion, correo de regalo, canje con saldo
parcial, combinacion con cupon, devolucion de saldo, retracto y contracargo."""
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone, translation

from . import facturacion, tarjetas_regalo
from .forms import GiftCardPurchaseForm
from .models import (
    Coupon,
    CouponDiscountType,
    GiftCard,
    GiftCardMovementKind,
    GiftCardStatus,
    OrderKind,
    OrderStatus,
    PaymentStatus,
)
from .services import (
    CheckoutError,
    InvalidOrderTransitionError,
    apply_order_status_transition,
    confirm_payment,
    create_gift_card_order,
    create_order_from_cart,
    registrar_pago_revertido,
    valid_next_statuses,
)
from .test_confirm_payment import DATOS, ConfirmPaymentBaseTestCase, _FakeTransaction

COMPRA = {
    'amount': Decimal('150000'), 'sender_name': 'Andrés', 'recipient_name': 'Laura',
    'recipient_email': 'laura@example.com', 'message': '¡Feliz cumpleaños!',
}
ENVIO_BOGOTA = Decimal('12000')  # tarifa de ciudad principal (ver shipping.services)


class _Base(ConfirmPaymentBaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def _comprar(self, **datos):
        with self.captureOnCommitCallbacks(execute=True):
            return create_gift_card_order(self.usuario, dict(COMPRA, **datos))

    def _tarjeta_activa(self, valor=Decimal('150000')):
        pedido = self._comprar(amount=valor)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        mail.outbox.clear()
        return GiftCard.objects.get(purchase_order=pedido)

    def _pedido(self, cantidad=1, **datos):
        with self.captureOnCommitCallbacks(execute=True):
            return create_order_from_cart(self.usuario, {str(self.variante.pk): cantidad}, dict(DATOS, **datos))


class CompraDeTarjetaTests(_Base):
    def test_la_compra_crea_un_pedido_sin_envio_y_una_tarjeta_pendiente(self):
        pedido = self._comprar()
        self.assertEqual(pedido.kind, OrderKind.GIFT_CARD)
        self.assertEqual(pedido.total, Decimal('150000.00'))
        self.assertEqual(pedido.shipping_cost, 0)
        self.assertFalse(hasattr(pedido, 'address'))
        tarjeta = pedido.purchased_gift_card
        self.assertEqual(tarjeta.status, GiftCardStatus.PENDING)
        self.assertFalse(tarjeta.is_usable())
        self.assertEqual(len(tarjeta.code), 16)
        self.assertEqual(tarjeta.recipient_email, 'laura@example.com')
        # Solo el aviso de compra recibida: el codigo todavia no sale a nadie.
        self.assertEqual([c.to for c in mail.outbox], [[self.usuario.email]])
        self.assertIn('laura@example.com', mail.outbox[0].body)
        self.assertNotIn(tarjeta.display_code, mail.outbox[0].body)

    def test_el_valor_debe_estar_entre_el_minimo_y_el_maximo(self):
        for valor in (Decimal('49999'), Decimal('1000001')):
            with self.subTest(valor=valor), self.assertRaises(CheckoutError):
                create_gift_card_order(self.usuario, dict(COMPRA, amount=valor))

    def test_el_pago_aprobado_activa_la_tarjeta_por_doce_meses_y_la_envia(self):
        pedido = self._comprar()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        pedido.refresh_from_db()
        tarjeta = pedido.purchased_gift_card
        tarjeta.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(tarjeta.status, GiftCardStatus.ACTIVE)
        self.assertTrue(tarjeta.is_usable())
        vence = timezone.localtime(tarjeta.expires_at).date()
        emitida = timezone.localtime(tarjeta.issued_at).date()
        self.assertEqual((vence.year - emitida.year) * 12 + vence.month - emitida.month, 12)
        self.assertIsNotNone(tarjeta.sent_at)
        self.assertEqual(tarjeta.movements.get().kind, GiftCardMovementKind.ISSUE)

        para_laura, para_comprador = mail.outbox
        self.assertEqual(para_laura.to, ['laura@example.com'])
        self.assertIn('Andrés te envió una tarjeta de regalo', para_laura.subject)
        self.assertIn(tarjeta.display_code, para_laura.body)
        self.assertIn('$150.000', para_laura.body)
        self.assertIn('¡Feliz cumpleaños!', para_laura.body)
        self.assertIn('vence el', para_laura.body)
        html = para_laura.alternatives[0][0]
        self.assertIn(tarjeta.display_code, html)
        self.assertIn('Válida hasta el', html)
        self.assertNotIn('font-style:italic', html)

        (nombre, contenido, tipo), = para_laura.attachments
        self.assertEqual((nombre, tipo), ('Tarjeta-de-regalo-GoToGym.pdf', 'application/pdf'))
        self.assertTrue(contenido.startswith(b'%PDF'))
        # Texto real, no una imagen: el codigo se puede seleccionar y copiar.
        import io

        from pypdf import PdfReader
        texto_del_pdf = PdfReader(io.BytesIO(contenido)).pages[0].extract_text()
        self.assertIn(tarjeta.display_code, texto_del_pdf)
        self.assertIn('Laura', texto_del_pdf)
        self.assertIn('Te adjuntamos la tarjeta en PDF', para_laura.body)

        self.assertEqual(para_comprador.to, [self.usuario.email])
        self.assertEqual(para_comprador.attachments, [])
        self.assertNotIn(tarjeta.display_code, para_comprador.body)
        self.assertIn(tarjeta.masked_code, para_comprador.body)

    def test_un_doble_aviso_de_pago_no_reenvia_ni_reemite_la_tarjeta(self):
        pedido = self._comprar()
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        self.assertEqual(mail.outbox, [])
        self.assertEqual(pedido.purchased_gift_card.movements.count(), 1)

    def test_si_el_pdf_falla_el_correo_sale_igual_sin_adjunto(self):
        from unittest.mock import patch

        pedido = self._comprar()
        mail.outbox.clear()
        with patch('orders.correos.tarjeta_pdf.pdf_de_tarjeta', side_effect=RuntimeError('sin fuente')):
            with self.captureOnCommitCallbacks(execute=True):
                confirm_payment(pedido, _FakeTransaction('approved'))
        para_laura = mail.outbox[0]
        self.assertEqual(para_laura.attachments, [])
        self.assertIn(pedido.purchased_gift_card.display_code, para_laura.body)

    def test_la_compra_no_se_factura(self):
        pedido = self._comprar()
        confirm_payment(pedido, _FakeTransaction('approved'))
        pedido.refresh_from_db()
        self.assertFalse(facturacion.facturable(pedido))

    def test_el_correo_de_regalo_sale_en_el_idioma_de_la_compra(self):
        with translation.override('en'):
            pedido = self._comprar()
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, _FakeTransaction('approved'))
        self.assertIn('sent you a GoToGym gift card', mail.outbox[0].subject)
        self.assertIn('Valid until', mail.outbox[0].alternatives[0][0])

    def test_un_pedido_sin_pagar_que_vence_anula_la_tarjeta(self):
        pedido = self._comprar()
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        tarjeta = GiftCard.objects.get(purchase_order=pedido)
        self.assertEqual(tarjeta.status, GiftCardStatus.CANCELLED)
        self.assertEqual(tarjeta.balance, 0)


class CanjeTests(_Base):
    def test_canje_parcial_deja_el_resto_del_saldo(self):
        tarjeta = self._tarjeta_activa(Decimal('500000'))
        pedido = self._pedido(gift_card_code=tarjeta.display_code)
        valor = Decimal('100000.00') + ENVIO_BOGOTA
        self.assertEqual(pedido.gift_card_total, valor)
        self.assertEqual(pedido.total, 0)
        self.assertEqual(pedido.order_value, valor)
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.balance, Decimal('500000') - valor)

    def test_si_el_saldo_no_alcanza_se_paga_la_diferencia(self):
        tarjeta = self._tarjeta_activa(Decimal('50000'))
        pedido = self._pedido(gift_card_code=tarjeta.code)
        self.assertEqual(pedido.gift_card_total, Decimal('50000.00'))
        self.assertEqual(pedido.total, Decimal('100000.00') + ENVIO_BOGOTA - Decimal('50000.00'))
        self.assertEqual(pedido.order_status, OrderStatus.PENDING_PAYMENT)
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.balance, 0)
        self.assertFalse(tarjeta.is_usable())

    def test_se_combina_con_un_cupon_que_se_aplica_primero(self):
        Coupon.objects.create(code='DIEZ', discount_type=CouponDiscountType.PERCENTAGE, value=Decimal('10'))
        tarjeta = self._tarjeta_activa(Decimal('50000'))
        pedido = self._pedido(coupon_code='DIEZ', gift_card_code=tarjeta.code)
        self.assertEqual(pedido.discount_total, Decimal('10000.00'))
        self.assertEqual(pedido.gift_card_total, Decimal('50000.00'))
        self.assertEqual(pedido.total, Decimal('100000.00') + ENVIO_BOGOTA - Decimal('10000.00') - Decimal('50000.00'))

    def test_si_la_tarjeta_cubre_todo_el_pedido_se_confirma_sin_pasarela(self):
        tarjeta = self._tarjeta_activa(Decimal('500000'))
        pedido = self._pedido(gift_card_code=tarjeta.code)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(pedido.payment_status, PaymentStatus.APPROVED)
        self.assertEqual(pedido.payment_transactions.count(), 0)
        self.assertEqual(self._stock(), 4)
        self.assertTrue(facturacion.facturable(pedido))

    def test_la_factura_del_canje_va_por_el_valor_completo(self):
        tarjeta = self._tarjeta_activa(Decimal('500000'))
        pedido = self._pedido(gift_card_code=tarjeta.code)
        cuerpo = facturacion.armar_factura(
            pedido, contacto_id=1, ids_de_items={self.variante.sku: 10, facturacion.REFERENCIA_ENVIO: 11},
        )
        producto, envio = cuerpo['items']
        self.assertEqual(producto['discount'], 0)
        self.assertGreater(producto['price'], 0)
        self.assertGreater(envio['price'], 0)
        self.assertIn(f'tarjeta de regalo {tarjeta.masked_code}', cuerpo['observations'])

    def test_una_tarjeta_vencida_no_se_acepta(self):
        tarjeta = self._tarjeta_activa()
        GiftCard.objects.filter(pk=tarjeta.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(CheckoutError):
            self._pedido(gift_card_code=tarjeta.code)

    def test_cancelar_el_pedido_devuelve_el_saldo_a_la_tarjeta(self):
        tarjeta = self._tarjeta_activa(Decimal('50000'))
        pedido = self._pedido(gift_card_code=tarjeta.code)
        with self.captureOnCommitCallbacks(execute=True):
            apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.balance, Decimal('50000'))
        self.assertTrue(tarjeta.is_usable())
        self.assertIn('volvió a su saldo', mail.outbox[-1].body)
        # Idempotente: volver a liberar no suma dos veces.
        tarjetas_regalo.devolver_saldo(pedido, 'otra vez')
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.balance, Decimal('50000'))

    def test_sin_stock_al_confirmar_el_saldo_vuelve_a_la_tarjeta(self):
        from unittest.mock import patch

        tarjeta = self._tarjeta_activa(Decimal('500000'))
        # Otra compra se lleva la ultima unidad entre el checkout y la
        # confirmacion: la comprobacion optimista del checkout no lo ve.
        self.variante.inventory.quantity_available = 0
        self.variante.inventory.save()
        with patch('orders.services._validar_disponibilidad'):
            pedido = self._pedido(gift_card_code=tarjeta.code)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.balance, Decimal('500000'))
        self.assertNotIn('Requiere reembolso manual', pedido.internal_note)

    def test_la_devolucion_del_pedido_devuelve_lo_pagado_con_tarjeta(self):
        tarjeta = self._tarjeta_activa(Decimal('500000'))
        pedido = self._pedido(gift_card_code=tarjeta.code)
        for estado in (OrderStatus.SHIPPED, OrderStatus.RETURNED):
            apply_order_status_transition(pedido, estado)
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.balance, Decimal('500000'))

    def test_el_campo_unico_reparte_cupon_y_tarjeta(self):
        from .forms import CheckoutForm

        Coupon.objects.create(code='DIEZ', discount_type=CouponDiscountType.PERCENTAGE, value=Decimal('10'))
        tarjeta = self._tarjeta_activa()
        form = CheckoutForm(dict(DATOS, discount_code=tarjeta.display_code.lower(), coupon_code='DIEZ'), user=self.usuario)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['gift_card_code'], tarjeta.code)
        self.assertEqual(form.cleaned_data['coupon_code'], 'DIEZ')
        form = CheckoutForm(dict(DATOS, discount_code='diez'), user=self.usuario)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['coupon_code'], 'DIEZ')

    def test_el_campo_unico_acepta_una_sola_tarjeta(self):
        from .forms import CheckoutForm

        primera, segunda = self._tarjeta_activa(), self._tarjeta_activa()
        form = CheckoutForm(dict(DATOS, gift_card_code=primera.code, discount_code=segunda.code), user=self.usuario)
        self.assertFalse(form.is_valid())
        self.assertIn('una tarjeta de regalo por pedido', form.errors['discount_code'][0])

    def test_la_vista_previa_unica_distingue_tarjeta_cupon_e_invalido(self):
        from carrito.services import write_cart

        Coupon.objects.create(code='DIEZ', discount_type=CouponDiscountType.PERCENTAGE, value=Decimal('10'))
        tarjeta = self._tarjeta_activa()
        self.client.force_login(self.usuario)
        sesion = self.client.session
        write_cart(sesion, {str(self.variante.pk): 1})
        sesion.save()
        url = reverse('orders:validar_codigo')
        datos = self.client.get(url, {'code': tarjeta.display_code}).json()
        self.assertEqual((datos['kind'], datos['code'], datos['balance']), ('gift_card', tarjeta.code, 150000.0))
        datos = self.client.get(url, {'code': 'diez'}).json()
        self.assertEqual((datos['kind'], datos['discount']), ('coupon', 10000.0))
        self.assertFalse(self.client.get(url, {'code': 'NOEXISTE'}).json()['valid'])

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_el_campo_unico_cuenta_los_codigos_de_tarjeta_inventados(self):
        url = reverse('orders:validar_codigo')
        self.client.force_login(self.usuario)
        for _ in range(tarjetas_regalo.INTENTOS_FALLIDOS_MAXIMOS):
            self.client.get(url, {'code': 'AAAABBBBCCCCDDDD'})
        self.assertIn('demasiados intentos', self.client.get(url, {'code': 'ZZZZYYYYXXXXWWWW'}).json()['message'])

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_demasiados_codigos_equivocados_bloquean_la_validacion(self):
        tarjeta = self._tarjeta_activa()
        url = reverse('orders:validar_tarjeta_regalo')
        self.client.force_login(self.usuario)
        for _ in range(tarjetas_regalo.INTENTOS_FALLIDOS_MAXIMOS):
            self.assertFalse(self.client.get(url, {'code': 'AAAABBBBCCCCDDDD'}).json()['valid'])
        respuesta = self.client.get(url, {'code': tarjeta.code}).json()
        self.assertFalse(respuesta['valid'])
        self.assertIn('demasiados intentos', respuesta['message'])

    def test_la_vista_previa_informa_saldo_y_vencimiento(self):
        tarjeta = self._tarjeta_activa()
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse('orders:validar_tarjeta_regalo'), {'code': tarjeta.display_code.lower()})
        datos = respuesta.json()
        self.assertTrue(datos['valid'])
        self.assertEqual(datos['balance'], 150000.0)
        self.assertEqual(datos['code'], tarjeta.display_code)

    def test_checkout_pagado_con_tarjeta_lleva_al_detalle_del_pedido(self):
        from carrito.services import write_cart

        tarjeta = self._tarjeta_activa(Decimal('500000'))
        self.client.force_login(self.usuario)
        sesion = self.client.session
        write_cart(sesion, {str(self.variante.pk): 1})
        sesion.save()
        respuesta = self.client.post(reverse('orders:checkout'), dict(DATOS, discount_code=tarjeta.display_code))
        pedido = self.usuario.orders.get(kind=OrderKind.PRODUCTS)
        self.assertRedirects(respuesta, reverse('orders:order_detail', args=[pedido.order_number]))
        detalle = self.client.get(respuesta.url)
        self.assertContains(detalle, 'Pagado con tarjeta de regalo')


class RetractoYContracargoTests(_Base):
    def test_una_tarjeta_sin_usar_admite_retracto(self):
        tarjeta = self._tarjeta_activa()
        compra = tarjeta.purchase_order
        self.assertEqual(valid_next_statuses(compra), [OrderStatus.CANCELLED])
        with self.captureOnCommitCallbacks(execute=True):
            apply_order_status_transition(compra, OrderStatus.CANCELLED)
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.status, GiftCardStatus.CANCELLED)
        self.assertEqual(tarjeta.balance, 0)
        self.assertEqual(tarjeta.movements.last().kind, GiftCardMovementKind.VOID)
        self.assertIn('tarjeta quedó anulada', mail.outbox[-1].body)

    def test_una_tarjeta_usada_no_admite_retracto(self):
        tarjeta = self._tarjeta_activa(Decimal('500000'))
        pedido = self._pedido(gift_card_code=tarjeta.code)
        # Aunque el pedido se cancele y el saldo vuelva, la tarjeta ya se uso.
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        compra = tarjeta.purchase_order
        self.assertEqual(valid_next_statuses(compra), [])
        with self.assertRaises(InvalidOrderTransitionError):
            apply_order_status_transition(compra, OrderStatus.CANCELLED)

    def test_un_contracargo_de_la_compra_bloquea_la_tarjeta(self):
        tarjeta = self._tarjeta_activa()
        registrar_pago_revertido(tarjeta.purchase_order, 'Contracargo de prueba.')
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.status, GiftCardStatus.DISABLED)
        self.assertEqual(tarjeta.balance, Decimal('150000'))
        self.assertIn('Contracargo de prueba.', tarjeta.disabled_reason)


class PaginaDeCompraTests(_Base):
    def test_la_pagina_se_ve_sin_sesion_y_pide_iniciar_sesion_para_comprar(self):
        respuesta = self.client.get(reverse('tarjeta_regalo'))
        self.assertContains(respuesta, 'Inicia sesión para comprar')
        self.assertContains(respuesta, '12 meses')
        respuesta = self.client.post(reverse('tarjeta_regalo'), {})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('commercial_login'), respuesta.url)

    def test_comprar_lleva_al_pago(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse('tarjeta_regalo'), {
            'amount': '$100.000', 'sender_name': 'Andrés', 'recipient_name': 'Laura',
            'recipient_email': 'Laura@Example.com', 'recipient_email_confirm': 'laura@example.com',
            'message': 'Para ti', 'accept_conditions': 'on',
        })
        pedido = self.usuario.orders.get()
        self.assertRedirects(respuesta, reverse('payments:pending', args=[pedido.order_number]), fetch_redirect_response=False)
        self.assertEqual(pedido.total, Decimal('100000.00'))
        self.assertEqual(pedido.purchased_gift_card.recipient_email, 'laura@example.com')
        pago = self.client.get(respuesta.url)
        self.assertEqual(pago.status_code, 200)
        self.assertNotContains(pago, 'Envío')

    def test_el_formulario_valida_correo_confirmado_rango_y_enlaces(self):
        form = GiftCardPurchaseForm({
            'amount': '20.000', 'sender_name': 'Andrés', 'recipient_name': 'Laura',
            'recipient_email': 'laura@example.com', 'recipient_email_confirm': 'otra@example.com',
            'message': 'Mira esto: www.sitio-raro.com', 'accept_conditions': '',
        })
        self.assertFalse(form.is_valid())
        self.assertEqual(
            set(form.errors), {'amount', 'recipient_email_confirm', 'message', 'accept_conditions'},
        )

    def test_el_vencimiento_cae_el_mismo_dia_un_ano_despues(self):
        emitida = timezone.make_aware(timezone.datetime(2028, 2, 29, 10, 0))
        vence = timezone.localtime(tarjetas_regalo.fecha_de_vencimiento(emitida))
        self.assertEqual((vence.year, vence.month, vence.day), (2029, 2, 28))
        self.assertEqual((vence.hour, vence.minute), (23, 59))
