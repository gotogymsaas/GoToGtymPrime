"""La etiqueta `imagen_producto` servia siempre desde static/product_media/,
asumiendo que toda foto de catalogo era un archivo empaquetado como
estatico con derivados pre-generados. Una imagen subida desde el panel
admin (ProductMedia/Product.image) vive en MEDIA_ROOT y nunca tiene
entrada en el manifiesto de derivados, asi que ese respaldo apuntaba a un
archivo que no existia -- la foto de cualquier producto creado o editado
desde el panel se veia rota en Store."""
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant

from tienda.templatetags.imagenes import imagen_producto

# Django aisla la base de datos en los tests, pero no el almacenamiento de
# archivos: una imagen subida en un test se escribe en el MEDIA_ROOT real
# si no se redirige aparte (mismo aislamiento que ya usa
# administracion/test_catalog_admin.py).
_MEDIA_ROOT_DE_PRUEBA = tempfile.mkdtemp(prefix='gotogym-test-media-')


class ImagenProductoTests(TestCase):
    def test_sin_entrada_en_el_manifiesto_usa_la_url_real_del_archivo(self):
        with patch('tienda.templatetags.imagenes.entrada', return_value=None):
            resultado = imagen_producto('products/subida-admin.jpg')
        self.assertEqual(resultado['respaldo'], '/media/products/subida-admin.jpg')
        self.assertEqual(resultado['fuentes'], [])

    def test_con_entrada_en_el_manifiesto_sigue_usando_el_derivado_estatico(self):
        registro = {
            'ancho': 100, 'alto': 100, 'nombre': 'product-media-products-viejo',
            'formatos': {'avif': [], 'webp': []},
        }
        with patch('tienda.templatetags.imagenes.entrada', return_value=registro):
            resultado = imagen_producto('products/viejo.jpg')
        self.assertTrue(resultado['respaldo'].startswith('/static/product_media/'))

    def test_sin_nombre_usa_el_placeholder(self):
        resultado = imagen_producto('')
        self.assertIn('placeholder', resultado['respaldo'])


@override_settings(MEDIA_ROOT=_MEDIA_ROOT_DE_PRUEBA)
class ImagenDeProductoNuevoEnStoreTests(TestCase):
    """Integracion de punta a punta: un producto creado sin manifiesto de
    derivados (cualquier producto subido desde el panel admin) debe pintar
    una URL de imagen realmente servible en la PLP."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA_ROOT_DE_PRUEBA, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            email='plp-imagen@example.com', username='plp-imagen@example.com', password='secret123',
        )
        self.client.force_login(self.usuario)

    def test_producto_con_imagen_subida_por_admin_no_apunta_a_static_product_media(self):
        categoria = ProductCategory.objects.create(name='Categoria imagen admin')
        marca = Brand.objects.create(name='Marca imagen admin')
        producto = Product.objects.create(
            name='Producto subido desde el panel', category=categoria, brand=marca,
            base_price=100000, stock=0,
        )
        media = ProductMedia.objects.create(
            product=producto,
            image=SimpleUploadedFile('nueva-foto.jpg', b'contenido', content_type='image/jpeg'),
            is_primary=True,
        )
        variante = ProductVariant.objects.create(product=producto, sku='NEWIMG-001', size='UNICA', color='negro')
        Inventory.objects.create(variant=variante, quantity_available=5)

        respuesta = self.client.get(reverse('tienda:producto_list'), {'filtro': 'Producto subido desde el panel'})

        self.assertContains(respuesta, media.image.url)
        self.assertNotContains(respuesta, '/static/product_media/')
