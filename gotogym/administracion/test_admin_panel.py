"""Panel admin: cupones, etiquetas de producto, inventario y gestion de
usuarios/roles. Cubre tanto el flujo normal como que un usuario sin permisos
de staff no pueda ejecutar estas operaciones llamando directamente a la URL."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from inventory.models import Inventory
from orders.models import Coupon
from products.models import Product, ProductCategory, ProductTag, ProductVariant


class PanelAdminBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            email='staff-panel@example.com', username='staff-panel@example.com',
            password='secret123', is_staff=True,
        )
        cls.cliente = User.objects.create_user(
            email='cliente-panel@example.com', username='cliente-panel@example.com',
            password='secret123',
        )

    def setUp(self):
        self.client.force_login(self.staff)


class ChromeDelPanelTests(PanelAdminBaseTestCase):
    """El "Salir" del panel no puede ser el mismo boton que cierra sesion
    (ver base.html): son dos acciones distintas, una vuelve a la tienda
    sin tocar la sesion, la otra la cierra de verdad. "Grupos y permisos"
    ya no tiene entrada en la navegacion (retirado temporalmente)."""

    def test_salir_del_panel_es_un_enlace_a_la_tienda_no_un_logout(self):
        respuesta = self.client.get(reverse('admin_dashboard'))
        self.assertContains(respuesta, f'href="{reverse("tienda:producto_list")}"')
        self.assertContains(respuesta, 'Salir del panel')
        self.assertContains(respuesta, 'Cerrar sesion')

    def test_salir_del_panel_no_cierra_la_sesion(self):
        self.client.get(reverse('tienda:producto_list'))
        respuesta = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(respuesta.status_code, 200)

    def test_cerrar_sesion_sigue_funcionando_por_separado(self):
        respuesta = self.client.post(reverse('logout'))
        self.assertEqual(respuesta.status_code, 302)
        respuesta_panel = self.client.get(reverse('admin_dashboard'))
        self.assertNotEqual(respuesta_panel.status_code, 200)

    def test_grupos_y_permisos_no_aparece_en_la_navegacion(self):
        respuesta = self.client.get(reverse('admin_dashboard'))
        self.assertNotContains(respuesta, 'Grupos y permisos')


class CuponesAdminTests(PanelAdminBaseTestCase):
    def test_crea_cupon_porcentaje(self):
        respuesta = self.client.post(reverse('admin_coupon_new'), {
            'code': 'VERANO20', 'discount_type': 'percentage', 'value': '20',
            'is_active': 'on',
        })
        self.assertRedirects(respuesta, reverse('admin_coupons'))
        cupon = Coupon.objects.get(code='VERANO20')
        self.assertEqual(cupon.value, Decimal('20'))
        self.assertTrue(cupon.is_usable())

    def test_codigo_duplicado_se_rechaza(self):
        Coupon.objects.create(code='DUPLICADO', discount_type='percentage', value=10)
        respuesta = self.client.post(reverse('admin_coupon_new'), {
            'code': 'duplicado', 'discount_type': 'percentage', 'value': '5',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe un cupon')

    def test_cupon_fuera_de_vigencia_no_es_usable(self):
        cupon = Coupon.objects.create(
            code='VENCIDO', discount_type='percentage', value=10,
            ends_at=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(cupon.is_usable())

    def test_toggle_desactiva_cupon(self):
        cupon = Coupon.objects.create(code='TOGGLE', discount_type='percentage', value=10)
        self.client.post(reverse('admin_coupon_toggle', args=[cupon.pk]))
        cupon.refresh_from_db()
        self.assertFalse(cupon.is_active)

    def test_eliminar_cupon(self):
        cupon = Coupon.objects.create(code='BORRAR', discount_type='percentage', value=10)
        self.client.post(reverse('admin_coupon_delete', args=[cupon.pk]))
        self.assertFalse(Coupon.objects.filter(pk=cupon.pk).exists())

    def test_usuario_sin_staff_no_puede_crear_cupon(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.post(reverse('admin_coupon_new'), {
            'code': 'HACKEO', 'discount_type': 'percentage', 'value': '99',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Coupon.objects.filter(code='HACKEO').exists())


class EtiquetasProductoAdminTests(PanelAdminBaseTestCase):
    def test_crea_etiqueta(self):
        respuesta = self.client.post(reverse('admin_catalogs'), {
            'kind': 'tag', 'tag-name': 'Edicion limitada', 'tag-color_token': 'gold',
        })
        self.assertRedirects(respuesta, reverse('admin_catalogs'))
        self.assertTrue(ProductTag.objects.filter(name='Edicion limitada').exists())

    def test_seed_de_badges_por_defecto_existe(self):
        for slug in ('best-seller', 'nuevo', 'oferta', 'destacado'):
            self.assertTrue(ProductTag.objects.filter(slug=slug).exists())

    def test_usuario_sin_staff_no_puede_crear_etiqueta(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.post(reverse('admin_catalogs'), {
            'kind': 'tag', 'tag-name': 'Hackeo', 'tag-color_token': 'gold',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(ProductTag.objects.filter(name='Hackeo').exists())


class InventarioAdminTests(PanelAdminBaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.categoria = ProductCategory.objects.create(name='Categoria inventario')
        cls.producto = Product.objects.create(
            name='Producto inventario', category=cls.categoria, base_price=Decimal('10000'),
        )
        cls.variante = ProductVariant.objects.create(
            product=cls.producto, sku='INV-001', size='M', color='Negro',
        )
        cls.inventario = Inventory.objects.create(variant=cls.variante, quantity_available=3)

        cls.otra_categoria = ProductCategory.objects.create(name='Otra categoria inventario')
        cls.otro_producto = Product.objects.create(
            name='Otro producto inventario', category=cls.otra_categoria, base_price=Decimal('20000'),
        )
        cls.otra_variante = ProductVariant.objects.create(
            product=cls.otro_producto, sku='INV-002', size='L', color='Azul',
        )
        Inventory.objects.create(variant=cls.otra_variante, quantity_available=15)

    def test_actualiza_stock(self):
        respuesta = self.client.post(
            reverse('admin_variant_stock_update', args=[self.variante.pk]),
            {'quantity_available': '25'},
        )
        self.assertRedirects(respuesta, reverse('admin_variants'))
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.quantity_available, 25)

    def test_rechaza_cantidad_negativa(self):
        self.client.post(
            reverse('admin_variant_stock_update', args=[self.variante.pk]),
            {'quantity_available': '-5'},
        )
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.quantity_available, 3)

    def test_filtro_stock_bajo(self):
        respuesta = self.client.get(reverse('admin_variants'), {'status': 'low'})
        self.assertContains(respuesta, 'INV-001')

    def test_filtro_por_categoria(self):
        respuesta = self.client.get(reverse('admin_variants'), {'categoria': self.categoria.pk})
        self.assertContains(respuesta, 'INV-001')
        self.assertNotContains(respuesta, 'INV-002')

    def test_filtro_por_talla(self):
        respuesta = self.client.get(reverse('admin_variants'), {'talla': 'L'})
        self.assertContains(respuesta, 'INV-002')
        self.assertNotContains(respuesta, 'INV-001')

    def test_filtro_por_color(self):
        respuesta = self.client.get(reverse('admin_variants'), {'color': 'Azul'})
        self.assertContains(respuesta, 'INV-002')
        self.assertNotContains(respuesta, 'INV-001')

    def test_filtros_combinados(self):
        # Categoria correcta pero talla que no le pertenece: no debe traer
        # nada, confirma que los filtros se combinan con AND, no con OR.
        respuesta = self.client.get(
            reverse('admin_variants'), {'categoria': self.categoria.pk, 'talla': 'L'},
        )
        self.assertNotContains(respuesta, 'INV-001')
        self.assertNotContains(respuesta, 'INV-002')

        respuesta_valida = self.client.get(
            reverse('admin_variants'), {'categoria': self.categoria.pk, 'talla': 'M', 'color': 'Negro'},
        )
        self.assertContains(respuesta_valida, 'INV-001')
        self.assertNotContains(respuesta_valida, 'INV-002')

    def test_usuario_sin_staff_no_puede_actualizar_stock(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.post(
            reverse('admin_variant_stock_update', args=[self.variante.pk]),
            {'quantity_available': '999'},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.quantity_available, 3)


class UsuariosRolesAdminTests(PanelAdminBaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        User = get_user_model()
        cls.otro_admin = User.objects.create_user(
            email='otro-admin@example.com', username='otro-admin@example.com',
            password='secret123', is_staff=True,
        )

    def test_asciende_usuario_a_influencer(self):
        respuesta = self.client.post(
            reverse('admin_user_role_update', args=[self.cliente.pk]), {'role': 'influencer'},
        )
        self.assertRedirects(respuesta, reverse('admin_users'))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.es_influencer)
        self.assertFalse(self.cliente.is_staff)

    def test_asciende_usuario_a_administrador(self):
        self.client.post(
            reverse('admin_user_role_update', args=[self.cliente.pk]), {'role': 'admin'},
        )
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.is_staff)

    def test_admin_no_puede_quitarse_su_propio_rol(self):
        respuesta = self.client.post(
            reverse('admin_user_role_update', args=[self.staff.pk]), {'role': 'user'},
        )
        self.assertRedirects(respuesta, reverse('admin_users'))
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_staff)

    def test_desactiva_y_reactiva_usuario(self):
        self.client.post(reverse('admin_user_toggle_active', args=[self.cliente.pk]))
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.is_active)
        self.client.post(reverse('admin_user_toggle_active', args=[self.cliente.pk]))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.is_active)

    def test_admin_no_puede_desactivarse_a_si_mismo(self):
        self.client.post(reverse('admin_user_toggle_active', args=[self.staff.pk]))
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_elimina_usuario(self):
        User = get_user_model()
        pk = self.cliente.pk
        self.client.post(reverse('admin_user_delete', args=[pk]))
        self.assertFalse(User.objects.filter(pk=pk).exists())

    def test_no_se_puede_eliminar_superusuario(self):
        User = get_user_model()
        superuser = User.objects.create_superuser(
            email='root-panel@example.com', username='root-panel@example.com', password='secret123',
        )
        self.client.post(reverse('admin_user_delete', args=[superuser.pk]))
        self.assertTrue(User.objects.filter(pk=superuser.pk).exists())

    def test_usuario_sin_staff_no_puede_cambiar_roles(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.post(
            reverse('admin_user_role_update', args=[self.otro_admin.pk]), {'role': 'user'},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.otro_admin.refresh_from_db()
        self.assertTrue(self.otro_admin.is_staff)
