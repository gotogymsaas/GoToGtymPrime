"""Programa de afiliados: solicitud y aprobacion, atribucion de ventas,
ciclo de vida de la comision y retiro de saldo.

Reemplaza el placeholder vacio que tenia esta app: antes de este cambio,
el panel del afiliado mostraba compras de ejemplo hardcodeadas en el
propio codigo (ver historial) y no habia ninguna prueba sobre el flujo
real.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from orders.models import Coupon, OrderStatus
from orders.services import (
    apply_order_status_transition,
    confirm_payment,
    create_order_from_cart,
    get_usable_coupon,
)
from products.models import Brand, Product, ProductCategory, ProductVariant

from .models import (
    Commission,
    CommissionStatus,
    InfluencerProfile,
    InfluencerProgramSettings,
    InfluencerStatus,
    ReferralClick,
    WithdrawalRequest,
    WithdrawalStatus,
)
from .services import (
    approve_influencer,
    deactivate_influencer,
    reject_influencer,
    request_withdrawal,
    resolve_withdrawal,
)

DATOS_ENTREGA = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


class _FakeTransaction:
    """Doble minimo de PaymentTransaction: confirm_payment solo mira `.status`."""

    def __init__(self, status):
        self.status = status


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class InfluencerTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.afiliado_user = User.objects.create_user(
            email='afiliado@example.com', username='afiliado@example.com', password='secret123',
        )
        cls.comprador = User.objects.create_user(
            email='comprador@example.com', username='comprador@example.com', password='secret123',
        )
        cls.admin = User.objects.create_user(
            email='admin@example.com', username='admin@example.com', password='secret123', is_staff=True,
        )
        categoria = ProductCategory.objects.create(name='Categoria influencer')
        marca = Brand.objects.create(name='Marca influencer')
        cls.producto = Product.objects.create(
            name='Producto influencer', category=categoria, brand=marca,
            base_price=Decimal('100000.0000'), stock=0,
        )
        cls.variante = _crear_variante(cls.producto, 'INF-001-S-NEG', 'S', 'negro', 10)

    def _crear_perfil_aprobado(self):
        perfil = InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.PENDING)
        approve_influencer(perfil, self.admin)
        perfil.refresh_from_db()
        return perfil

    def _crear_pedido_referido(self, perfil, cantidad=1):
        cupon = perfil.coupons.first()
        datos = dict(DATOS_ENTREGA, coupon_code=cupon.code)
        return create_order_from_cart(self.comprador, {str(self.variante.pk): cantidad}, datos)

    def _pedido_entregado(self, perfil):
        pedido = self._crear_pedido_referido(perfil)
        confirm_payment(pedido, _FakeTransaction('approved'))
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        return pedido


class SolicitudDeAfiliacionTests(InfluencerTestBase):
    def test_suscribirse_crea_perfil_pendiente_sin_activar_rol(self):
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('influencer_suscribete'), {'accept_terms': '1', 'referral_code': 'MIMARCA2026'})

        perfil = InfluencerProfile.objects.get(user=self.afiliado_user)
        self.assertEqual(perfil.status, InfluencerStatus.PENDING)
        self.assertEqual(perfil.referral_code, 'MIMARCA2026')
        self.assertIsNotNone(perfil.terms_accepted_at)
        self.afiliado_user.refresh_from_db()
        self.assertFalse(self.afiliado_user.es_influencer)

    def test_el_codigo_propuesto_debe_ser_valido(self):
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('influencer_suscribete'), {'accept_terms': '1', 'referral_code': 'a b!'})

        self.assertFalse(InfluencerProfile.objects.filter(user=self.afiliado_user).exists())

    def test_el_codigo_propuesto_debe_estar_disponible(self):
        InfluencerProfile.objects.create(user=self.comprador, referral_code='OCUPADO1')
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('influencer_suscribete'), {'accept_terms': '1', 'referral_code': 'ocupado1'})

        self.assertFalse(InfluencerProfile.objects.filter(user=self.afiliado_user).exists())

    def test_no_se_puede_suscribir_sin_aceptar_terminos(self):
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('influencer_suscribete'), {})

        self.assertFalse(InfluencerProfile.objects.filter(user=self.afiliado_user).exists())

    def test_get_muestra_el_formulario_de_postulacion(self):
        self.client.force_login(self.afiliado_user)
        respuesta = self.client.get(reverse('influencer_suscribete'))
        self.assertContains(respuesta, 'accept_terms')

    def test_aprobado_activo_no_ve_el_formulario_sino_su_dashboard(self):
        self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)
        respuesta = self.client.get(reverse('influencer_suscribete'))
        self.assertRedirects(respuesta, reverse('influencer_dashboard'))

    def test_aprobar_activa_el_rol_y_genera_un_cupon_usable(self):
        perfil = InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.PENDING)
        approve_influencer(perfil, self.admin)

        self.afiliado_user.refresh_from_db()
        self.assertTrue(self.afiliado_user.es_influencer)
        cupon = Coupon.objects.get(influencer=perfil)
        self.assertEqual(cupon.code, perfil.referral_code)
        self.assertTrue(cupon.is_active)

    def test_reaprobar_con_codigo_nuevo_actualiza_el_cupon_existente(self):
        perfil = InfluencerProfile.objects.create(
            user=self.afiliado_user, status=InfluencerStatus.PENDING, referral_code='PRIMERCODIGO',
        )
        approve_influencer(perfil, self.admin)
        deactivate_influencer(perfil)

        perfil.referral_code = 'CODIGONUEVO'
        perfil.status = InfluencerStatus.PENDING
        perfil.save(update_fields=['referral_code', 'status'])
        approve_influencer(perfil, self.admin)

        cupon = Coupon.objects.get(influencer=perfil)
        self.assertEqual(cupon.code, 'CODIGONUEVO')
        self.assertTrue(cupon.is_active)

    def test_rechazar_no_activa_el_rol_ni_genera_cupon(self):
        perfil = InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.PENDING)
        reject_influencer(perfil, self.admin)

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, InfluencerStatus.REJECTED)
        self.afiliado_user.refresh_from_db()
        self.assertFalse(self.afiliado_user.es_influencer)
        self.assertFalse(Coupon.objects.filter(influencer=perfil).exists())

    def test_reaprobar_reactiva_el_cupon_existente_en_lugar_de_duplicarlo(self):
        perfil = self._crear_perfil_aprobado()
        deactivate_influencer(perfil)
        approve_influencer(perfil, self.admin)

        self.assertEqual(Coupon.objects.filter(influencer=perfil).count(), 1)
        self.assertTrue(Coupon.objects.get(influencer=perfil).is_active)

    def test_cancelar_suscripcion_desactiva_el_cupon(self):
        perfil = self._crear_perfil_aprobado()
        deactivate_influencer(perfil)

        self.assertFalse(Coupon.objects.get(influencer=perfil).is_active)
        self.afiliado_user.refresh_from_db()
        self.assertFalse(self.afiliado_user.es_influencer)


class AtribucionYComisionTests(InfluencerTestBase):
    def test_pedido_con_cupon_de_afiliado_queda_referido(self):
        perfil = self._crear_perfil_aprobado()
        pedido = self._crear_pedido_referido(perfil)
        self.assertEqual(pedido.referred_by_id, perfil.pk)

    def test_pago_aprobado_genera_comision_pendiente_sobre_el_neto(self):
        perfil = self._crear_perfil_aprobado()
        pedido = self._crear_pedido_referido(perfil)
        confirm_payment(pedido, _FakeTransaction('approved'))

        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.status, CommissionStatus.PENDING)
        tasa = InfluencerProgramSettings.load().default_commission_rate
        esperado = ((pedido.subtotal - pedido.discount_total) * tasa / Decimal('100')).quantize(Decimal('0.01'))
        self.assertEqual(comision.amount, esperado)

    def test_la_tasa_propia_del_afiliado_tiene_prioridad_sobre_la_global(self):
        perfil = self._crear_perfil_aprobado()
        perfil.commission_rate = Decimal('25.00')
        perfil.save(update_fields=['commission_rate'])
        pedido = self._crear_pedido_referido(perfil)

        confirm_payment(pedido, _FakeTransaction('approved'))

        comision = Commission.objects.get(order=pedido)
        esperado = ((pedido.subtotal - pedido.discount_total) * Decimal('25.00') / Decimal('100')).quantize(Decimal('0.01'))
        self.assertEqual(comision.amount, esperado)

    def test_pedido_sin_cupon_no_genera_comision(self):
        pedido = create_order_from_cart(self.comprador, {str(self.variante.pk): 1}, DATOS_ENTREGA)
        confirm_payment(pedido, _FakeTransaction('approved'))
        self.assertFalse(Commission.objects.filter(order=pedido).exists())

    def test_entregado_aprueba_la_comision_y_pasa_al_balance_disponible(self):
        perfil = self._crear_perfil_aprobado()
        pedido = self._pedido_entregado(perfil)

        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.status, CommissionStatus.APPROVED)
        perfil.refresh_from_db()
        self.assertEqual(perfil.commission_balance, comision.amount)
        self.assertEqual(perfil.total_referred, 1)
        self.assertEqual(perfil.total_sales, pedido.subtotal)

    def test_cancelado_revierte_la_comision_y_vacia_el_balance(self):
        perfil = self._crear_perfil_aprobado()
        pedido = self._crear_pedido_referido(perfil)
        confirm_payment(pedido, _FakeTransaction('approved'))

        apply_order_status_transition(pedido, OrderStatus.CANCELLED)

        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.status, CommissionStatus.REVERTED)
        perfil.refresh_from_db()
        self.assertEqual(perfil.commission_balance, Decimal('0.00'))


class RetiroDeComisionesTests(InfluencerTestBase):
    def test_solicitar_retiro_reserva_las_comisiones_aprobadas(self):
        perfil = self._crear_perfil_aprobado()
        pedido = self._pedido_entregado(perfil)
        comision = Commission.objects.get(order=pedido)

        solicitud = request_withdrawal(perfil)

        self.assertEqual(solicitud.amount, comision.amount)
        perfil.refresh_from_db()
        self.assertEqual(perfil.commission_balance, Decimal('0.00'))

    def test_sin_comisiones_disponibles_no_crea_solicitud(self):
        perfil = self._crear_perfil_aprobado()
        self.assertIsNone(request_withdrawal(perfil))

    def test_resolver_como_pagada_marca_las_comisiones_pagadas(self):
        perfil = self._crear_perfil_aprobado()
        pedido = self._pedido_entregado(perfil)
        solicitud = request_withdrawal(perfil)

        resolve_withdrawal(solicitud, True, self.admin)

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.status, WithdrawalStatus.PAID)
        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.PAID)

    def test_rechazar_solicitud_devuelve_la_comision_al_balance(self):
        perfil = self._crear_perfil_aprobado()
        self._pedido_entregado(perfil)
        solicitud = request_withdrawal(perfil)
        monto = solicitud.amount

        resolve_withdrawal(solicitud, False, self.admin)

        perfil.refresh_from_db()
        self.assertEqual(perfil.commission_balance, monto)

    def test_no_se_puede_pedir_dos_retiros_pendientes_a_la_vez(self):
        perfil = self._crear_perfil_aprobado()
        self._pedido_entregado(perfil)
        self.client.force_login(self.afiliado_user)

        self.client.post(reverse('influencer_solicitar_retiro'))
        self.client.post(reverse('influencer_solicitar_retiro'))

        self.assertEqual(WithdrawalRequest.objects.filter(influencer=perfil).count(), 1)


class PanelDeAfiliadoViewTests(InfluencerTestBase):
    def test_dashboard_de_pendiente_no_expone_codigo_de_referido(self):
        InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.PENDING)
        self.client.force_login(self.afiliado_user)

        respuesta = self.client.get(reverse('influencer_dashboard'))

        self.assertContains(respuesta, 'en revision')
        self.assertNotContains(respuesta, 'Copiar')

    def test_dashboard_de_aprobado_muestra_las_compras_reales(self):
        perfil = self._crear_perfil_aprobado()
        pedido = self._crear_pedido_referido(perfil)
        confirm_payment(pedido, _FakeTransaction('approved'))
        self.client.force_login(self.afiliado_user)

        respuesta = self.client.get(reverse('influencer_dashboard'))

        self.assertContains(respuesta, pedido.order_number)

    def test_ya_no_hay_compras_hardcodeadas_de_ejemplo(self):
        self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)

        respuesta = self.client.get(reverse('influencer_compras_referidas'))

        self.assertNotContains(respuesta, 'Ana Pérez')
        self.assertNotContains(respuesta, 'Luis Gómez')


class PanelAdminDeAfiliadosTests(InfluencerTestBase):
    def setUp(self):
        super().setUp()
        from administracion.permissions import grant_full_admin_permissions
        grant_full_admin_permissions(self.admin)

    def test_staff_puede_aprobar_una_solicitud(self):
        perfil = InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.PENDING)
        self.client.force_login(self.admin)

        self.client.post(reverse('admin_influencer_approve', args=[perfil.pk]))

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, InfluencerStatus.APPROVED)

    def test_staff_con_grupo_sin_el_permiso_no_puede_aprobar(self):
        staff_sin_permiso = get_user_model().objects.create_user(
            email='staff2@example.com', username='staff2@example.com', password='secret123', is_staff=True,
        )
        staff_sin_permiso.groups.add(Group.objects.create(name='Grupo sin permisos de afiliados'))
        perfil = InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.PENDING)
        self.client.force_login(staff_sin_permiso)

        self.client.post(reverse('admin_influencer_approve', args=[perfil.pk]))

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, InfluencerStatus.PENDING)

    def test_staff_puede_marcar_un_retiro_como_pagado(self):
        perfil = self._crear_perfil_aprobado()
        self._pedido_entregado(perfil)
        solicitud = request_withdrawal(perfil)
        self.client.force_login(self.admin)

        self.client.post(reverse('admin_withdrawal_resolve', args=[solicitud.pk]), {'action': 'pay'})

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.status, WithdrawalStatus.PAID)


class ControlDeAutorreferenciaTests(InfluencerTestBase):
    """RF-F11: nadie puede usar su propio codigo de afiliado."""

    def test_get_usable_coupon_rechaza_al_dueno_del_cupon(self):
        perfil = self._crear_perfil_aprobado()
        cupon = perfil.coupons.first()

        self.assertIsNone(get_usable_coupon(cupon.code, user=self.afiliado_user))
        self.assertIsNotNone(get_usable_coupon(cupon.code, user=self.comprador))

    def test_el_afiliado_no_puede_comprar_con_su_propio_codigo(self):
        perfil = self._crear_perfil_aprobado()
        cupon = perfil.coupons.first()
        datos = dict(DATOS_ENTREGA, email=self.afiliado_user.email, coupon_code=cupon.code)

        pedido = create_order_from_cart(self.afiliado_user, {str(self.variante.pk): 1}, datos)

        self.assertIsNone(pedido.referred_by_id)
        self.assertEqual(pedido.discount_total, Decimal('0.00'))

    def test_validar_cupon_en_vivo_rechaza_la_autorreferencia(self):
        perfil = self._crear_perfil_aprobado()
        cupon = perfil.coupons.first()
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('carrito:add_to_cart', args=[self.variante.pk]))

        respuesta = self.client.get(reverse('orders:validar_cupon'), {'code': cupon.code})

        self.assertFalse(respuesta.json()['valid'])


class TrackingDeClicsTests(InfluencerTestBase):
    """A6: metricas de rendimiento basadas en el enlace de referido."""

    def test_visitar_la_tienda_con_ref_registra_un_clic(self):
        perfil = self._crear_perfil_aprobado()
        cupon = perfil.coupons.first()

        self.client.get(reverse('tienda:producto_list'), {'ref': cupon.code})

        self.assertEqual(ReferralClick.objects.filter(influencer=perfil).count(), 1)

    def test_recargar_la_pagina_en_la_misma_sesion_no_duplica_el_clic(self):
        perfil = self._crear_perfil_aprobado()
        cupon = perfil.coupons.first()

        self.client.get(reverse('tienda:producto_list'), {'ref': cupon.code})
        self.client.get(reverse('tienda:producto_list'), {'ref': cupon.code})

        self.assertEqual(ReferralClick.objects.filter(influencer=perfil).count(), 1)

    def test_codigo_invalido_no_registra_clic(self):
        self.client.get(reverse('tienda:producto_list'), {'ref': 'NOEXISTE'})
        self.assertEqual(ReferralClick.objects.count(), 0)

    def test_el_ref_precarga_el_cupon_en_el_checkout(self):
        perfil = self._crear_perfil_aprobado()
        cupon = perfil.coupons.first()
        self.client.force_login(self.comprador)
        self.client.get(reverse('tienda:producto_list'), {'ref': cupon.code})
        self.client.post(reverse('carrito:add_to_cart', args=[self.variante.pk]))

        respuesta = self.client.get(reverse('orders:checkout'))

        self.assertContains(respuesta, cupon.code)

    def test_dashboard_muestra_clics_y_tasa_de_conversion(self):
        perfil = self._crear_perfil_aprobado()
        cupon = perfil.coupons.first()
        self.client.get(reverse('tienda:producto_list'), {'ref': cupon.code})
        self._pedido_entregado(perfil)
        self.client.force_login(self.afiliado_user)

        respuesta = self.client.get(reverse('influencer_dashboard'))

        self.assertContains(respuesta, '100.0%')
