"""Panel administrativo: catalogos (categorias, marcas, etiquetas), cupones y
programa de afiliados. Cubre el flujo normal, los filtros de listado y que un
miembro del personal sin el permiso concreto no pueda ejecutar la accion."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from influencer.models import (
    InfluencerProfile,
    InfluencerProgramSettings,
    InfluencerStatus,
    WithdrawalRequest,
    WithdrawalStatus,
)
from orders.models import Coupon
from products.models import Brand, Product, ProductCategory, ProductTag


def _mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class BaseAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.superusuario = User.objects.create_superuser(
            email='root-cat@example.com', username='root-cat@example.com', password='secret123',
        )
        cls.sin_permisos = User.objects.create_user(
            email='staff-sin@example.com', username='staff-sin@example.com', password='secret123', is_staff=True,
        )
        # Un staff sin ningun Grupo se considera cuenta heredada y recibe todos
        # los permisos al entrar al panel; pertenecer a un Grupo vacio es lo que
        # lo deja como rol intermedio sin permisos.
        cls.sin_permisos.groups.add(Group.objects.create(name='Solo lectura'))
        cls.cliente = User.objects.create_user(
            email='cliente-cat@example.com', username='cliente-cat@example.com', password='secret123',
        )

    def setUp(self):
        self.client.force_login(self.superusuario)

    def _como_personal_sin_permisos(self):
        self.client.force_login(self.sin_permisos)


class CatalogosTests(BaseAdminTests):
    def test_crear_categoria_marca_y_etiqueta(self):
        url = reverse('admin_catalogs')
        self.client.post(url, {'kind': 'category', 'category-name': 'Leggins'})
        self.client.post(url, {'kind': 'brand', 'brand-name': 'GoToGym Lab'})
        self.client.post(url, {'kind': 'tag', 'tag-name': 'Etiqueta de prueba', 'tag-color_token': 'accent'})

        self.assertTrue(ProductCategory.objects.filter(name='Leggins').exists())
        self.assertTrue(Brand.objects.filter(name='GoToGym Lab').exists())
        self.assertTrue(ProductTag.objects.filter(name='Etiqueta de prueba').exists())

    def test_un_formulario_invalido_vuelve_a_mostrar_el_error_sin_crear_nada(self):
        respuesta = self.client.post(reverse('admin_catalogs'), {'kind': 'brand', 'brand-name': ''})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Brand.objects.filter(name='').exists())

    def test_sin_permiso_no_se_crea_nada(self):
        self._como_personal_sin_permisos()
        respuesta = self.client.post(reverse('admin_catalogs'), {'kind': 'category', 'category-name': 'Prohibida'})
        self.assertIn('No tienes permisos', _mensajes(respuesta)[-1])
        self.assertFalse(ProductCategory.objects.filter(name='Prohibida').exists())

    def test_activar_desactivar_y_eliminar_etiqueta(self):
        etiqueta = ProductTag.objects.create(name='Etiqueta temporal', color_token='accent')
        self.client.post(reverse('admin_tag_toggle', args=[etiqueta.pk]))
        etiqueta.refresh_from_db()
        self.assertFalse(etiqueta.is_active)
        self.client.post(reverse('admin_tag_toggle', args=[etiqueta.pk]))
        etiqueta.refresh_from_db()
        self.assertTrue(etiqueta.is_active)

        self.client.post(reverse('admin_tag_delete', args=[etiqueta.pk]))
        self.assertFalse(ProductTag.objects.filter(pk=etiqueta.pk).exists())

    def test_eliminar_categoria_o_marca_sin_productos(self):
        categoria = ProductCategory.objects.create(name='Vacia')
        marca = Brand.objects.create(name='Sin productos')
        self.client.post(reverse('admin_category_delete', args=[categoria.pk]))
        self.client.post(reverse('admin_brand_delete', args=[marca.pk]))
        self.assertFalse(ProductCategory.objects.filter(pk=categoria.pk).exists())
        self.assertFalse(Brand.objects.filter(pk=marca.pk).exists())

    def test_no_se_elimina_categoria_ni_marca_con_productos(self):
        categoria = ProductCategory.objects.create(name='Con productos')
        marca = Brand.objects.create(name='Marca con productos')
        Product.objects.create(name='P', category=categoria, brand=marca, base_price=Decimal('1000'), stock=0)

        r1 = self.client.post(reverse('admin_category_delete', args=[categoria.pk]))
        r2 = self.client.post(reverse('admin_brand_delete', args=[marca.pk]))

        self.assertIn('productos asociados', _mensajes(r1)[-1])
        self.assertIn('productos asociados', _mensajes(r2)[-1])
        self.assertTrue(ProductCategory.objects.filter(pk=categoria.pk).exists())
        self.assertTrue(Brand.objects.filter(pk=marca.pk).exists())

    def test_eliminar_exige_el_permiso_correspondiente(self):
        marca = Brand.objects.create(name='Protegida')
        self._como_personal_sin_permisos()
        self.client.post(reverse('admin_brand_delete', args=[marca.pk]))
        self.assertTrue(Brand.objects.filter(pk=marca.pk).exists())


class CuponesListadoTests(BaseAdminTests):
    def setUp(self):
        super().setUp()
        Coupon.objects.create(code='VERANO10', value=Decimal('10'), is_active=True)
        Coupon.objects.create(code='INVIERNO5', value=Decimal('5'), is_active=False)

    def _codigos(self, **params):
        respuesta = self.client.get(reverse('admin_coupons'), params)
        return {c.code for c in respuesta.context['page_obj']}

    def test_filtros_por_texto_y_estado(self):
        self.assertGreaterEqual(self._codigos(), {'VERANO10', 'INVIERNO5'})
        self.assertEqual(self._codigos(q='verano'), {'VERANO10'})
        self.assertIn('VERANO10', self._codigos(status='active'))
        self.assertNotIn('INVIERNO5', self._codigos(status='active'))
        self.assertIn('INVIERNO5', self._codigos(status='inactive'))
        self.assertNotIn('VERANO10', self._codigos(status='inactive'))

    def test_el_formulario_de_cupon_se_muestra_y_el_codigo_repetido_se_rechaza(self):
        self.assertEqual(self.client.get(reverse('admin_coupon_new')).status_code, 200)
        respuesta = self.client.post(
            reverse('admin_coupon_new'),
            {'code': 'VERANO10', 'discount_type': 'percentage', 'value': '10', 'is_active': 'on'},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Coupon.objects.filter(code='VERANO10').count(), 1)


class AfiliadosAdminTests(BaseAdminTests):
    def setUp(self):
        super().setUp()
        self.perfil = InfluencerProfile.objects.create(user=self.cliente, status=InfluencerStatus.PENDING)

    def test_listado_filtra_por_estado_y_texto(self):
        url = reverse('admin_influencers')
        self.assertContains(self.client.get(url, {'status': 'pending'}), self.cliente.email)
        self.assertNotContains(self.client.get(url, {'status': 'rejected'}), self.cliente.email)
        self.assertContains(self.client.get(url, {'q': 'cliente-cat'}), self.cliente.email)
        self.assertNotContains(self.client.get(url, {'q': 'inexistente'}), self.cliente.email)

    def test_listado_filtra_las_solicitudes_de_comision_por_estado(self):
        solicitud = WithdrawalRequest.objects.create(influencer=self.perfil, amount=Decimal('5000'))
        respuesta = self.client.get(reverse('admin_influencers'), {'wstatus': WithdrawalStatus.PAID})
        self.assertNotIn(solicitud, list(respuesta.context['withdrawal_page_obj']))
        respuesta = self.client.get(reverse('admin_influencers'))
        self.assertIn(solicitud, list(respuesta.context['withdrawal_page_obj']))

    def test_actualizar_la_configuracion_del_programa(self):
        url = reverse('admin_influencer_settings_update')
        self.client.post(url, {'default_commission_rate': '12.50', 'default_customer_discount': '8.00'})
        self.assertEqual(InfluencerProgramSettings.load().default_commission_rate, Decimal('12.50'))

        respuesta = self.client.post(url, {'default_commission_rate': 'abc', 'default_customer_discount': ''})
        self.assertIn('No se pudo guardar', _mensajes(respuesta)[-1])
        self.assertEqual(InfluencerProgramSettings.load().default_commission_rate, Decimal('12.50'))

    def test_detalle_de_afiliado_con_conversion(self):
        self.perfil.referral_clicks.create()
        self.perfil.referral_clicks.create()
        self.perfil.total_referred = 1
        self.perfil.save(update_fields=['total_referred'])
        respuesta = self.client.get(reverse('admin_influencer_detail', args=[self.perfil.pk]))
        self.assertEqual(respuesta.context['conversion_rate'], '50.0')

    def test_detalle_sin_clics_no_calcula_conversion(self):
        respuesta = self.client.get(reverse('admin_influencer_detail', args=[self.perfil.pk]))
        self.assertIsNone(respuesta.context['conversion_rate'])

    def test_tasa_propia_valida_e_invalida(self):
        url = reverse('admin_influencer_commission_rate_update', args=[self.perfil.pk])
        self.client.post(url, {'commission_rate': '15.00'})
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.commission_rate, Decimal('15.00'))

        respuesta = self.client.post(url, {'commission_rate': 'mucho'})
        self.assertIn('No se pudo guardar', _mensajes(respuesta)[-1])

    def test_aprobar_rechazar_y_desactivar(self):
        self.client.post(reverse('admin_influencer_approve', args=[self.perfil.pk]))
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.status, InfluencerStatus.APPROVED)

        self.client.post(reverse('admin_influencer_deactivate', args=[self.perfil.pk]))
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_active)

        self.client.post(reverse('admin_influencer_reject', args=[self.perfil.pk]))
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.status, InfluencerStatus.REJECTED)

    def test_aprobar_vuelve_a_la_pagina_de_origen_solo_si_es_del_mismo_sitio(self):
        url = reverse('admin_influencer_approve', args=[self.perfil.pk])
        destino = reverse('admin_influencer_detail', args=[self.perfil.pk])
        self.assertRedirects(
            self.client.post(url, {'next': destino}), destino, fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.post(url, {'next': 'https://sitio-malicioso.example/'}), reverse('admin_influencers'),
            fetch_redirect_response=False,
        )

    def test_pagar_y_rechazar_solicitud_de_comision(self):
        pagar = WithdrawalRequest.objects.create(influencer=self.perfil, amount=Decimal('5000'))
        rechazar = WithdrawalRequest.objects.create(influencer=self.perfil, amount=Decimal('3000'))

        r1 = self.client.post(reverse('admin_withdrawal_resolve', args=[pagar.pk]), {'action': 'pay'})
        r2 = self.client.post(reverse('admin_withdrawal_resolve', args=[rechazar.pk]), {'action': 'reject'})

        pagar.refresh_from_db()
        rechazar.refresh_from_db()
        self.assertEqual(pagar.status, WithdrawalStatus.PAID)
        self.assertEqual(rechazar.status, WithdrawalStatus.REJECTED)
        self.assertIn('pagada', _mensajes(r1)[-1])
        self.assertIn('rechazada', _mensajes(r2)[-1])

    def test_rutas_antiguas_de_comisiones_llevan_a_afiliados(self):
        self.assertRedirects(
            self.client.get(reverse('admin_withdrawals')), reverse('admin_influencers'), fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get('/es/admin-panel/retiros/'), reverse('admin_influencers'), fetch_redirect_response=False,
        )

    def test_eliminar_afiliado(self):
        self.client.post(reverse('admin_influencer_delete', args=[self.perfil.pk]))
        self.assertFalse(InfluencerProfile.objects.filter(pk=self.perfil.pk).exists())

    def test_sin_permiso_no_se_puede_aprobar_ni_eliminar(self):
        self._como_personal_sin_permisos()
        self.client.post(reverse('admin_influencer_approve', args=[self.perfil.pk]))
        self.client.post(reverse('admin_influencer_delete', args=[self.perfil.pk]))
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.status, InfluencerStatus.PENDING)
