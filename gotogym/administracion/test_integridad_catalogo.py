"""Borrado seguro de productos y trazabilidad del pedido en el panel."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from orders.models import OrderStatus
from orders.services import apply_order_status_transition, confirm_payment, create_order_from_cart
from products.models import Product, ProductCategory, ProductVariant

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


class _PagoAprobado:
    status = 'approved'


class CatalogoProtegidoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            email='root-integridad@example.com', username='root-integridad@example.com', password='secret123',
        )
        cls.categoria = ProductCategory.objects.create(name='Categoria integridad')
        cls.producto = Product.objects.create(
            name='Producto integridad', category=cls.categoria, base_price=Decimal('50000'),
        )
        cls.variante = ProductVariant.objects.create(product=cls.producto, sku='INT-001', size='M', color='negro')
        Inventory.objects.create(variant=cls.variante, quantity_available=5)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_borrar_una_categoria_con_productos_esta_protegido_en_la_base(self):
        with self.assertRaises(ProtectedError):
            self.categoria.delete()
        self.assertTrue(Product.objects.filter(pk=self.producto.pk).exists())

    def test_un_producto_sin_ventas_se_elimina(self):
        respuesta = self.client.post(reverse('admin_product_delete', args=[self.producto.pk]))
        self.assertRedirects(respuesta, reverse('admin_products'))
        self.assertFalse(Product.objects.filter(pk=self.producto.pk).exists())

    def test_un_producto_con_ventas_se_desactiva_en_vez_de_borrarse(self):
        create_order_from_cart(self.admin, {str(self.variante.pk): 1}, DATOS)

        respuesta = self.client.post(reverse('admin_product_delete', args=[self.producto.pk]))

        self.assertRedirects(respuesta, reverse('admin_products'))
        self.assertTrue(Product.objects.filter(pk=self.producto.pk).exists())
        self.variante.refresh_from_db()
        self.assertFalse(self.variante.is_active)
        self.assertTrue(Inventory.objects.filter(variant=self.variante).exists())


class HistorialEnElPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            email='root-historial@example.com', username='root-historial@example.com', password='secret123',
        )
        categoria = ProductCategory.objects.create(name='Categoria historial')
        producto = Product.objects.create(name='Producto historial', category=categoria, base_price=Decimal('50000'))
        variante = ProductVariant.objects.create(product=producto, sku='HIS-001', size='M', color='negro')
        Inventory.objects.create(variant=variante, quantity_available=5)
        cls.pedido = create_order_from_cart(cls.admin, {str(variante.pk): 1}, DATOS)

    def test_el_detalle_muestra_quien_hizo_cada_cambio(self):
        confirm_payment(self.pedido, _PagoAprobado())
        apply_order_status_transition(self.pedido, OrderStatus.PREPARING, changed_by=self.admin)
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse('admin_order_detail', args=[self.pedido.order_number]))

        self.assertContains(respuesta, 'Historial del pedido')
        self.assertContains(respuesta, 'root-historial@example.com')
        self.assertContains(respuesta, 'Sistema')

    def test_cambiar_el_estado_desde_el_panel_registra_al_usuario(self):
        confirm_payment(self.pedido, _PagoAprobado())
        self.client.force_login(self.admin)

        self.client.post(
            reverse('admin_order_update_status', args=[self.pedido.order_number]),
            {'order_status': OrderStatus.PREPARING},
        )

        registro = self.pedido.status_history.latest('id')
        self.assertEqual(registro.to_status, OrderStatus.PREPARING)
        self.assertEqual(registro.changed_by, self.admin)
