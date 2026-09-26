"""Panel admin de catalogo: alta de producto con variantes, media e
inventario, sin tocar la base de datos ni ejecutar migraciones."""
import io
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from inventory.models import Inventory
from orders.models import Order
from orders.services import create_order_from_cart
from PIL import Image
from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant

DATOS_PEDIDO = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


def _imagen():
    """PNG 1x1 real generado con Pillow, para probar la subida de
    ProductMedia sin depender de un archivo externo."""
    buffer = io.BytesIO()
    Image.new('RGB', (1, 1), color='white').save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile('test.png', buffer.read(), content_type='image/png')


# Django reemplaza la base de datos por una version efimera durante los
# tests, pero NO hace lo mismo con el almacenamiento de archivos: una imagen
# subida en un test se escribe en el MEDIA_ROOT real. Sin este aislamiento,
# cada corrida de esta suite deja PNG huerfanos en gotogym/media/products/.
_MEDIA_ROOT_DE_PRUEBA = tempfile.mkdtemp(prefix='gotogym-test-media-')


@override_settings(MEDIA_ROOT=_MEDIA_ROOT_DE_PRUEBA)
class CatalogAdminTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA_ROOT_DE_PRUEBA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria admin catalogo')
        cls.marca = Brand.objects.create(name='Marca admin catalogo')
        User = get_user_model()
        cls.staff = User.objects.create_user(
            email='staff-catalogo@example.com', username='staff-catalogo@example.com',
            password='secret123', is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def _formset_management(self, total=1, initial=0):
        return {
            'variants-TOTAL_FORMS': str(total),
            'variants-INITIAL_FORMS': str(initial),
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
        }


class AltaCompletaDeProductoTests(CatalogAdminTestCase):
    """Producto + variantes + imagen + stock inicial, sin tocar la base de
    datos directamente: primero se crea el producto, luego se le agregan
    variantes e imagenes desde la misma pantalla de edicion."""

    def test_crear_producto_luego_agregarle_una_variante_con_stock(self):
        response = self.client.post(reverse('admin_product_new'), {
            'name': 'Producto nuevo desde admin',
            'category': self.categoria.pk,
            'brand': self.marca.pk,
            'description': 'Descripcion de prueba',
            'base_price': '150000',
            'discount': '0',
            'stock': '0',
            'featured': '',
        })
        producto = Product.objects.get(name='Producto nuevo desde admin')
        self.assertRedirects(response, reverse('admin_product_edit', args=[producto.pk]))

        data = {
            'name': producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': producto.description, 'base_price': '150000', 'discount': '0',
            'stock': '0', 'featured': '',
            'variants-0-sku': 'NEW-001-S-NEG',
            'variants-0-size': 'S',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '10',
            **self._formset_management(total=1, initial=0),
        }
        self.client.post(reverse('admin_product_edit', args=[producto.pk]), data)

        variante = ProductVariant.objects.get(sku='NEW-001-S-NEG')
        self.assertEqual(variante.product, producto)
        self.assertEqual(Inventory.objects.get(variant=variante).quantity_available, 10)

    def test_agregar_imagen_a_un_producto(self):
        producto = Product.objects.create(
            name='Producto con imagen', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0,
        )
        response = self.client.post(
            reverse('admin_product_media_add', args=[producto.pk]),
            {'image': _imagen(), 'alt_text': 'Foto de prueba', 'sort_order': '0', 'is_primary': 'on'},
        )
        self.assertRedirects(response, reverse('admin_product_edit', args=[producto.pk]))
        media = ProductMedia.objects.get(product=producto)
        self.assertTrue(media.is_primary)

    def test_marcar_una_imagen_como_principal_desmarca_las_demas(self):
        producto = Product.objects.create(
            name='Producto dos imagenes', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0,
        )
        primera = ProductMedia.objects.create(product=producto, image=_imagen(), is_primary=True)

        self.client.post(
            reverse('admin_product_media_add', args=[producto.pk]),
            {'image': _imagen(), 'alt_text': '', 'sort_order': '1', 'is_primary': 'on'},
        )

        primera.refresh_from_db()
        self.assertFalse(primera.is_primary)
        self.assertEqual(ProductMedia.objects.filter(product=producto, is_primary=True).count(), 1)

    def test_eliminar_imagen(self):
        producto = Product.objects.create(
            name='Producto para borrar imagen', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0,
        )
        media = ProductMedia.objects.create(product=producto, image=_imagen())

        self.client.post(reverse('admin_product_media_delete', args=[producto.pk, media.pk]))
        self.assertFalse(ProductMedia.objects.filter(pk=media.pk).exists())


class SkuDuplicadoTests(CatalogAdminTestCase):
    def setUp(self):
        super().setUp()
        self.producto = Product.objects.create(
            name='Producto SKU', category=self.categoria, brand=self.marca,
            base_price=Decimal('70000.0000'), stock=0,
        )
        self.existente = ProductVariant.objects.create(
            product=self.producto, sku='DUP-001-S-NEG', size='S', color='negro',
        )
        Inventory.objects.create(variant=self.existente, quantity_available=5)

    def test_no_se_puede_crear_una_variante_con_sku_ya_usado(self):
        data = {
            'name': self.producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '70000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-id': str(self.existente.pk),
            'variants-0-sku': 'DUP-001-S-NEG',
            'variants-0-size': 'S',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '5',
            'variants-1-sku': 'DUP-001-S-NEG',
            'variants-1-size': 'M',
            'variants-1-color': 'negro',
            'variants-1-price_override': '',
            'variants-1-is_active': 'on',
            'variants-1-quantity_available': '5',
            **self._formset_management(total=2, initial=1),
        }
        response = self.client.post(reverse('admin_product_edit', args=[self.producto.pk]), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProductVariant.objects.filter(sku='DUP-001-S-NEG').count(), 1)

    def test_el_error_de_sku_no_deja_un_500(self):
        data = {
            'name': self.producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '70000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-id': str(self.existente.pk),
            'variants-0-sku': 'DUP-001-S-NEG',
            'variants-0-size': 'S',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '5',
            'variants-1-sku': 'DUP-001-S-NEG',
            'variants-1-size': 'L',
            'variants-1-color': 'negro',
            'variants-1-price_override': '',
            'variants-1-is_active': 'on',
            'variants-1-quantity_available': '5',
            **self._formset_management(total=2, initial=1),
        }
        response = self.client.post(reverse('admin_product_edit', args=[self.producto.pk]), data)
        self.assertIn(response.status_code, (200, 302))


class EliminarVarianteReferenciadaTests(CatalogAdminTestCase):
    def setUp(self):
        super().setUp()
        self.producto = Product.objects.create(
            name='Producto vendido', category=self.categoria, brand=self.marca,
            base_price=Decimal('55000.0000'), stock=0,
        )
        self.variante = ProductVariant.objects.create(
            product=self.producto, sku='SOLD-001-S-NEG', size='S', color='negro',
        )
        Inventory.objects.create(variant=self.variante, quantity_available=5)

    def _eliminar(self):
        data = {
            'name': self.producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '55000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-id': str(self.variante.pk),
            'variants-0-sku': self.variante.sku,
            'variants-0-size': 'S',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '5',
            'variants-0-DELETE': 'on',
            **self._formset_management(total=1, initial=1),
        }
        return self.client.post(reverse('admin_product_edit', args=[self.producto.pk]), data)

    def test_variante_sin_ventas_se_elimina_de_verdad(self):
        self._eliminar()
        self.assertFalse(ProductVariant.objects.filter(pk=self.variante.pk).exists())

    def test_variante_con_pedido_no_se_borra_sino_que_se_desactiva(self):
        User = get_user_model()
        cliente = User.objects.create_user(
            email='cliente-vendido@example.com', username='cliente-vendido@example.com',
            password='secret123',
        )
        create_order_from_cart(cliente, {str(self.variante.pk): 1}, DATOS_PEDIDO)

        self._eliminar()

        self.variante.refresh_from_db()
        self.assertFalse(self.variante.is_active)
        # El historico de la orden sigue intacto: la fila no se borro.
        self.assertTrue(ProductVariant.objects.filter(pk=self.variante.pk).exists())
        pedido = Order.objects.get()
        self.assertEqual(pedido.items.get().variant_id, self.variante.pk)
