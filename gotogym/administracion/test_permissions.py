"""Permisos granulares del panel admin: roles intermedios via Grupo, el
auto-sanado de cuentas is_staff legadas, la configuracion general del
panel y el reordenamiento de imagenes de producto por drag-and-drop."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from products.models import Product, ProductCategory, ProductMedia

from .models import PanelSettings
from .permissions import ADMIN_PERM_CODENAMES, admin_permission_queryset


class AutoSanadoDeAdminsLegadosTests(TestCase):
    """Una cuenta is_staff creada antes de este sistema de permisos (por
    ejemplo directo en el ORM, como se hacia antes) debe seguir teniendo
    acceso completo la primera vez que usa el panel, sin migracion previa."""

    def setUp(self):
        User = get_user_model()
        self.legado = User.objects.create_user(
            email='legado@example.com', username='legado@example.com',
            password='secret123', is_staff=True,
        )
        self.client.force_login(self.legado)

    def test_no_tiene_permisos_de_panel_recien_creado(self):
        self.assertFalse(self.legado.has_perms(ADMIN_PERM_CODENAMES))

    def test_una_peticion_al_panel_le_completa_los_permisos(self):
        self.client.get(reverse('admin_dashboard'))
        self.legado.refresh_from_db()
        self.assertTrue(self.legado.has_perms(ADMIN_PERM_CODENAMES))

    def test_puede_operar_una_seccion_protegida_en_la_misma_peticion_que_lo_sana(self):
        # No hace falta una segunda visita: el auto-sanado y el permiso
        # recien otorgado tienen que valer dentro de la misma peticion.
        respuesta = self.client.post(reverse('admin_coupon_new'), {
            'code': 'SANADO', 'discount_type': 'percentage', 'value': '10',
        })
        self.assertRedirects(respuesta, reverse('admin_coupons'))

    def test_superusuario_no_necesita_el_paquete_de_permisos(self):
        User = get_user_model()
        superuser = User.objects.create_superuser(
            email='root-sano@example.com', username='root-sano@example.com', password='secret123',
        )
        self.client.force_login(superuser)
        self.client.get(reverse('admin_dashboard'))
        superuser.refresh_from_db()
        # `has_perms` siempre da True para un superusuario (Django lo
        # resuelve asi sin mirar la tabla): lo que importa aqui es que el
        # auto-sanado no le haya asignado el paquete de permisos en la BD,
        # porque un superusuario no lo necesita.
        self.assertFalse(superuser.user_permissions.exists())
        # Y aun asi pasa cualquier chequeo de permiso del panel.
        respuesta = self.client.post(reverse('admin_coupon_new'), {
            'code': 'ROOT', 'discount_type': 'percentage', 'value': '10',
        })
        self.assertRedirects(respuesta, reverse('admin_coupons'))


class RolIntermedioViaGrupoTests(TestCase):
    """Un usuario staff sin el rol Administrador completo, pero con un
    Grupo que solo trae un permiso puntual, debe poder usar exactamente esa
    seccion y ninguna otra."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(
            email='admin-grupos@example.com', username='admin-grupos@example.com',
            password='secret123', is_staff=True,
        )
        cls.soporte = User.objects.create_user(
            email='soporte@example.com', username='soporte@example.com',
            password='secret123', is_staff=True,
        )
        cls.grupo = Group.objects.create(name='Soporte inventario')
        cls.grupo.permissions.add(
            Permission.objects.get(content_type__app_label='inventory', codename='change_inventory'),
        )
        cls.soporte.groups.add(cls.grupo)

        categoria = ProductCategory.objects.create(name='Categoria permisos')
        cls.producto = Product.objects.create(
            name='Producto permisos', category=categoria, base_price=Decimal('10000'),
        )

    def setUp(self):
        self.client.force_login(self.soporte)

    def test_puede_usar_la_seccion_cubierta_por_su_grupo(self):
        from inventory.models import Inventory
        from products.models import ProductVariant

        variante = ProductVariant.objects.create(
            product=self.producto, sku='PERM-001', size='M', color='Negro',
        )
        Inventory.objects.create(variant=variante, quantity_available=1)

        respuesta = self.client.post(
            reverse('admin_variant_stock_update', args=[variante.pk]),
            {'quantity_available': '50'},
        )
        self.assertRedirects(respuesta, reverse('admin_variants'))

    def test_no_puede_usar_una_seccion_fuera_de_su_grupo(self):
        respuesta = self.client.post(reverse('admin_product_delete', args=[self.producto.pk]))
        self.assertRedirects(respuesta, reverse('admin_dashboard'))
        self.assertTrue(Product.objects.filter(pk=self.producto.pk).exists())

    def test_puede_ver_listados_de_solo_lectura_por_ser_staff(self):
        # Las secciones de solo lectura (dashboard, listados) no exigen un
        # permiso puntual: cualquier staff puede verlas.
        respuesta = self.client.get(reverse('admin_products'))
        self.assertEqual(respuesta.status_code, 200)

    def test_admin_puede_asignar_el_grupo_a_otro_usuario(self):
        self.client.force_login(self.admin)
        User = get_user_model()
        objetivo = User.objects.create_user(
            email='nuevo-soporte@example.com', username='nuevo-soporte@example.com',
            password='secret123', is_staff=True,
        )
        respuesta = self.client.post(
            reverse('admin_user_groups_update', args=[objetivo.pk]), {'groups': [self.grupo.pk]},
        )
        self.assertRedirects(respuesta, reverse('admin_users'))
        self.assertIn(self.grupo, objetivo.groups.all())


class GruposYPermisosAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(
            email='admin-grupos2@example.com', username='admin-grupos2@example.com',
            password='secret123', is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    # "Grupos y permisos" ya no tiene enlace en la navegacion del panel
    # (retirado temporalmente de la interfaz), pero sus rutas y vistas
    # siguen activas -- por eso estas pruebas todavia pasan por
    # `reverse()` normal, no por acceso directo a la vista.

    def test_crea_grupo_con_permisos(self):
        permiso = Permission.objects.get(content_type__app_label='orders', codename='add_coupon')
        respuesta = self.client.post(reverse('admin_group_new'), {
            'name': 'Marketing', 'permissions': [permiso.pk],
        })
        self.assertRedirects(respuesta, reverse('admin_groups'))
        grupo = Group.objects.get(name='Marketing')
        self.assertIn(permiso, grupo.permissions.all())

    def test_solo_ofrece_el_catalogo_curado_de_permisos(self):
        respuesta = self.client.get(reverse('admin_group_new'))
        opciones = respuesta.context['form'].fields['permissions'].queryset
        self.assertEqual(set(opciones), set(admin_permission_queryset()))

    def test_elimina_grupo(self):
        grupo = Group.objects.create(name='Temporal')
        self.client.post(reverse('admin_group_delete', args=[grupo.pk]))
        self.assertFalse(Group.objects.filter(pk=grupo.pk).exists())

    def test_staff_con_rol_intermedio_no_puede_crear_grupos(self):
        # Un staff con un Grupo acotado (rol intermedio) no se auto-sana a
        # permisos completos: si su grupo no incluye auth.add_group, no
        # puede crear otros grupos.
        User = get_user_model()
        staff_acotado = User.objects.create_user(
            email='staff-acotado@example.com', username='staff-acotado@example.com',
            password='secret123', is_staff=True,
        )
        grupo_limitado = Group.objects.create(name='Solo cupones')
        grupo_limitado.permissions.add(
            Permission.objects.get(content_type__app_label='orders', codename='add_coupon'),
        )
        staff_acotado.groups.add(grupo_limitado)
        self.client.force_login(staff_acotado)

        respuesta = self.client.post(reverse('admin_group_new'), {'name': 'Hackeo', 'permissions': []})
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Group.objects.filter(name='Hackeo').exists())
        # Pero si puede seguir usando lo que su grupo si cubre.
        respuesta_cupon = self.client.post(reverse('admin_coupon_new'), {
            'code': 'ACOTADO', 'discount_type': 'percentage', 'value': '5',
        })
        self.assertRedirects(respuesta_cupon, reverse('admin_coupons'))


class ConfiguracionDelPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(
            email='admin-config@example.com', username='admin-config@example.com',
            password='secret123', is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_umbral_por_defecto_es_cinco(self):
        self.assertEqual(PanelSettings.load().low_stock_threshold, 5)

    def test_actualiza_el_umbral_de_stock_bajo(self):
        respuesta = self.client.post(reverse('admin_inventory_threshold_update'), {'low_stock_threshold': '10'})
        self.assertRedirects(respuesta, reverse('admin_variants'))
        self.assertEqual(PanelSettings.load().low_stock_threshold, 10)

    def test_dashboard_usa_el_umbral_configurado(self):
        from inventory.models import Inventory

        # El catalogo semilla ya trae variantes con stock variado, asi que
        # el umbral configurado se compara contra la misma consulta que
        # hace la vista, en vez de un numero absoluto adivinado a mano.
        for umbral in (3, 10):
            PanelSettings.objects.update_or_create(pk=1, defaults={'low_stock_threshold': umbral})
            esperado = Inventory.objects.filter(
                quantity_available__gt=0, quantity_available__lte=umbral,
            ).count()
            respuesta = self.client.get(reverse('admin_dashboard'))
            self.assertEqual(respuesta.context['low_stock_count'], esperado)

    def test_usuario_sin_permiso_no_puede_cambiar_el_umbral(self):
        User = get_user_model()
        cliente = User.objects.create_user(
            email='cliente-config@example.com', username='cliente-config@example.com', password='secret123',
        )
        self.client.force_login(cliente)
        respuesta = self.client.post(reverse('admin_inventory_threshold_update'), {'low_stock_threshold': '99'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(PanelSettings.load().low_stock_threshold, 5)


class ReordenarImagenesDeProductoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(
            email='admin-reorden@example.com', username='admin-reorden@example.com',
            password='secret123', is_staff=True,
        )
        categoria = ProductCategory.objects.create(name='Categoria reorden')
        cls.producto = Product.objects.create(
            name='Producto reorden', category=categoria, base_price=Decimal('10000'),
        )
        cls.media_1 = ProductMedia.objects.create(product=cls.producto, image='products/uno.jpg', sort_order=0)
        cls.media_2 = ProductMedia.objects.create(product=cls.producto, image='products/dos.jpg', sort_order=1)
        cls.media_3 = ProductMedia.objects.create(product=cls.producto, image='products/tres.jpg', sort_order=2)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_persiste_el_nuevo_orden(self):
        respuesta = self.client.post(
            reverse('admin_product_media_reorder', args=[self.producto.pk]),
            {'media_id': [str(self.media_3.pk), str(self.media_1.pk), str(self.media_2.pk)]},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.media_1.refresh_from_db()
        self.media_2.refresh_from_db()
        self.media_3.refresh_from_db()
        self.assertEqual(self.media_3.sort_order, 0)
        self.assertEqual(self.media_1.sort_order, 1)
        self.assertEqual(self.media_2.sort_order, 2)

    def test_ignora_ids_de_otro_producto(self):
        otra_categoria = ProductCategory.objects.create(name='Categoria ajena')
        otro_producto = Product.objects.create(
            name='Producto ajeno', category=otra_categoria, base_price=Decimal('5000'),
        )
        media_ajena = ProductMedia.objects.create(product=otro_producto, image='products/ajena.jpg', sort_order=0)

        self.client.post(
            reverse('admin_product_media_reorder', args=[self.producto.pk]),
            {'media_id': [str(media_ajena.pk), str(self.media_1.pk)]},
        )
        media_ajena.refresh_from_db()
        self.assertEqual(media_ajena.sort_order, 0)

    def test_usuario_sin_permiso_no_puede_reordenar(self):
        User = get_user_model()
        cliente = User.objects.create_user(
            email='cliente-reorden@example.com', username='cliente-reorden@example.com', password='secret123',
        )
        self.client.force_login(cliente)
        respuesta = self.client.post(
            reverse('admin_product_media_reorder', args=[self.producto.pk]),
            {'media_id': [str(self.media_2.pk), str(self.media_1.pk)]},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.media_1.refresh_from_db()
        self.assertEqual(self.media_1.sort_order, 0)
