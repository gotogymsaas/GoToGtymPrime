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
from products.variant_parsing import build_sku

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
            'variants-0-size': 'S',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '10',
            **self._formset_management(total=1, initial=0),
        }
        self.client.post(reverse('admin_product_edit', args=[producto.pk]), data)

        variante = producto.variants.get(size='S', color='negro')
        self.assertEqual(variante.sku, build_sku(producto.pk, 'S', 'negro'))
        self.assertEqual(Inventory.objects.get(variant=variante).quantity_available, 10)

    def test_crear_producto_y_su_variante_en_la_misma_peticion(self):
        # Antes, un producto recien creado no mostraba la tabla de
        # variantes hasta un segundo viaje al servidor: si el usuario no
        # volvia a esa pantalla, el producto quedaba sin ninguna variante
        # ni Inventory, y por lo tanto invisible en Inventario. Ahora el
        # POST de creacion puede traer la variante de una vez.
        data = {
            'name': 'Producto un solo paso', 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '80000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-size': 'UNICA',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '7',
            **self._formset_management(total=1, initial=0),
        }
        response = self.client.post(reverse('admin_product_new'), data)

        producto = Product.objects.get(name='Producto un solo paso')
        self.assertRedirects(response, reverse('admin_product_edit', args=[producto.pk]))
        variante = producto.variants.get()
        self.assertEqual(variante.size, 'UNICA')
        self.assertEqual(variante.color, 'negro')
        self.assertEqual(variante.sku, build_sku(producto.pk, 'UNICA', 'negro'))
        self.assertEqual(Inventory.objects.get(variant=variante).quantity_available, 7)

    def test_crear_producto_sin_llenar_variantes_le_crea_una_por_defecto(self):
        # El formulario superior (nombre, precio, stock, tags) no toca
        # Inventario: solo lo hace la tabla de variantes. Si el admin lo
        # deja vacio, el producto se guardaba sin ninguna variante y por
        # lo tanto no habia nada que gestionar en Inventario -- se le crea
        # una generica (UNICA/UNICO) con el stock que ya puso arriba, para
        # que cualquier producto creado sea gestionable de inmediato.
        response = self.client.post(reverse('admin_product_new'), {
            'name': 'Producto sin variantes explicitas',
            'category': self.categoria.pk,
            'brand': self.marca.pk,
            'description': '',
            'base_price': '90000',
            'discount': '0',
            'stock': '8',
            'featured': '',
        })
        producto = Product.objects.get(name='Producto sin variantes explicitas')
        self.assertRedirects(response, reverse('admin_product_edit', args=[producto.pk]))

        variante = producto.variants.get()
        self.assertEqual(variante.size, 'UNICA')
        self.assertEqual(variante.color, 'UNICO')
        self.assertEqual(Inventory.objects.get(variant=variante).quantity_available, 8)

        # Debe aparecer en el listado de Inventario.
        respuesta_inventario = self.client.get(reverse('admin_variants'), {'q': variante.sku})
        self.assertContains(respuesta_inventario, variante.sku)

    def test_no_duplica_la_variante_por_defecto_si_ya_hay_una_real(self):
        data = {
            'name': 'Producto con variante real', 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '80000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-size': 'M',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '3',
            **self._formset_management(total=1, initial=0),
        }
        self.client.post(reverse('admin_product_new'), data)

        producto = Product.objects.get(name='Producto con variante real')
        self.assertEqual(producto.variants.count(), 1)
        self.assertEqual(producto.variants.get().sku, build_sku(producto.pk, 'M', 'negro'))

    def test_crear_producto_con_varias_variantes_agregadas_en_el_mismo_envio(self):
        # Simula lo que hace el boton "+ Agregar variante" del lado del
        # cliente: agrega filas al formset clonando el formulario vacio, sin
        # tocar las que ya existian. Aqui se manda directo un TOTAL_FORMS
        # mayor a 1 con varias filas nuevas, que es lo que ese boton produce.
        data = {
            'name': 'Producto con varias tallas', 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '60000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-size': 'S', 'variants-0-color': 'negro',
            'variants-0-price_override': '', 'variants-0-is_active': 'on', 'variants-0-quantity_available': '4',
            'variants-1-size': 'M', 'variants-1-color': 'negro',
            'variants-1-price_override': '', 'variants-1-is_active': 'on', 'variants-1-quantity_available': '6',
            'variants-2-size': 'L', 'variants-2-color': 'blanco',
            'variants-2-price_override': '', 'variants-2-is_active': 'on', 'variants-2-quantity_available': '2',
            **self._formset_management(total=3, initial=0),
        }
        response = self.client.post(reverse('admin_product_new'), data)

        producto = Product.objects.get(name='Producto con varias tallas')
        self.assertRedirects(response, reverse('admin_product_edit', args=[producto.pk]))
        self.assertEqual(producto.variants.count(), 3)

        for size, color, stock in [('S', 'negro', 4), ('M', 'negro', 6), ('L', 'blanco', 2)]:
            variante = producto.variants.get(size=size, color=color)
            self.assertEqual(variante.sku, build_sku(producto.pk, size, color))
            self.assertEqual(Inventory.objects.get(variant=variante).quantity_available, stock)

    def test_la_talla_debe_ser_una_de_las_opciones_validas(self):
        data = {
            'name': 'Producto talla invalida', 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '80000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-size': 'XXXL-inventada',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '1',
            **self._formset_management(total=1, initial=0),
        }
        self.client.post(reverse('admin_product_new'), data)

        producto = Product.objects.get(name='Producto talla invalida')
        self.assertEqual(producto.variants.count(), 0)

    def test_la_pantalla_de_edicion_ofrece_las_tallas_estandar(self):
        producto = Product.objects.create(
            name='Producto tallas estandar', category=self.categoria, brand=self.marca,
            base_price=Decimal('80000.0000'), stock=0,
        )
        response = self.client.get(reverse('admin_product_edit', args=[producto.pk]))
        for talla in ('XS', 'S', 'M', 'L', 'XL', 'UNICA'):
            self.assertContains(response, f'<option value="{talla}">{talla}</option>')

    def test_la_talla_ya_guardada_aparece_seleccionada_al_editar(self):
        producto = Product.objects.create(
            name='Producto talla seleccionada', category=self.categoria, brand=self.marca,
            base_price=Decimal('80000.0000'), stock=0,
        )
        ProductVariant.objects.create(product=producto, sku='SEL-001', size='L', color='negro')

        response = self.client.get(reverse('admin_product_edit', args=[producto.pk]))
        self.assertContains(response, '<option value="L" selected>L</option>')

    def test_agregar_imagen_a_un_producto(self):
        # Sin alt_text/orden/"principal" que llenar: la primera foto de un
        # producto sin ninguna galeria previa queda como la que se ve
        # (Product.primary_image cae en la primera por orden cuando nada
        # tiene is_primary explicito), sin que el admin tenga que marcarla.
        producto = Product.objects.create(
            name='Producto con imagen', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0,
        )
        response = self.client.post(
            reverse('admin_product_media_add', args=[producto.pk]),
            {'image': _imagen()},
        )
        self.assertRedirects(response, reverse('admin_product_edit', args=[producto.pk]))
        media = ProductMedia.objects.get(product=producto)
        self.assertEqual(media.sort_order, 0)
        self.assertEqual(producto.primary_image, media.image)

    def test_agregar_varias_imagenes_de_una_vez(self):
        producto = Product.objects.create(
            name='Producto varias imagenes', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0,
        )
        response = self.client.post(
            reverse('admin_product_media_add', args=[producto.pk]),
            {'image': [_imagen(), _imagen(), _imagen()]},
        )
        self.assertRedirects(response, reverse('admin_product_edit', args=[producto.pk]))
        medios = list(ProductMedia.objects.filter(product=producto).order_by('sort_order'))
        self.assertEqual(len(medios), 3)
        self.assertEqual([m.sort_order for m in medios], [0, 1, 2])

    def test_agregar_mas_imagenes_las_pone_al_final_de_la_galeria_existente(self):
        producto = Product.objects.create(
            name='Producto con galeria previa', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0,
        )
        ProductMedia.objects.create(product=producto, image=_imagen(), sort_order=0)
        ProductMedia.objects.create(product=producto, image=_imagen(), sort_order=1)

        self.client.post(
            reverse('admin_product_media_add', args=[producto.pk]),
            {'image': _imagen()},
        )

        nueva = ProductMedia.objects.filter(product=producto).order_by('-sort_order').first()
        self.assertEqual(nueva.sort_order, 2)
        self.assertEqual(producto.media.count(), 3)

    def test_eliminar_imagen(self):
        producto = Product.objects.create(
            name='Producto para borrar imagen', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0,
        )
        media = ProductMedia.objects.create(product=producto, image=_imagen())

        self.client.post(reverse('admin_product_media_delete', args=[producto.pk, media.pk]))
        self.assertFalse(ProductMedia.objects.filter(pk=media.pk).exists())


class PrecioEnPesosSinDecimalesTests(CatalogAdminTestCase):
    """El campo de precio ya no acepta ni muestra decimales (nadie transa
    centavos de peso), y admite el punto de miles que el navegador muestra
    mientras se escribe ("300.000") -- el servidor lo limpia antes de
    guardar."""

    def test_acepta_el_precio_con_puntos_de_miles(self):
        response = self.client.post(reverse('admin_product_new'), {
            'name': 'Producto con precio formateado', 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '1.250.000', 'discount': '0', 'stock': '0', 'featured': '',
        })
        producto = Product.objects.get(name='Producto con precio formateado')
        self.assertRedirects(response, reverse('admin_product_edit', args=[producto.pk]))
        self.assertEqual(producto.base_price, Decimal('1250000'))

    def test_el_formulario_muestra_el_precio_ya_guardado_con_puntos_de_miles(self):
        producto = Product.objects.create(
            name='Producto precio existente', category=self.categoria, brand=self.marca,
            base_price=Decimal('1250000.0000'), stock=0,
        )
        response = self.client.get(reverse('admin_product_edit', args=[producto.pk]))
        self.assertContains(response, 'value="1.250.000"')

    def test_rechaza_un_precio_vacio(self):
        response = self.client.post(reverse('admin_product_new'), {
            'name': 'Producto sin precio', 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '', 'discount': '0', 'stock': '0', 'featured': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(name='Producto sin precio').exists())

    def test_precio_propio_de_variante_tambien_acepta_puntos_de_miles(self):
        producto = Product.objects.create(
            name='Producto variante precio propio', category=self.categoria, brand=self.marca,
            base_price=Decimal('80000.0000'), stock=0,
        )
        data = {
            'name': producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '80000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-size': 'M', 'variants-0-color': 'negro',
            'variants-0-price_override': '95.000', 'variants-0-is_active': 'on',
            'variants-0-quantity_available': '3',
            **self._formset_management(total=1, initial=0),
        }
        self.client.post(reverse('admin_product_edit', args=[producto.pk]), data)

        variante = producto.variants.get()
        self.assertEqual(variante.price_override, Decimal('95000'))


class UnificacionDeImagenDeProductoTests(CatalogAdminTestCase):
    """La pantalla de edicion tenia dos formularios de imagen sobre el
    mismo producto: `Product.image` (arriba) y la galeria `ProductMedia`
    (abajo). Ahora la galeria es la unica fuente; estos casos cubren tanto
    el formulario (ya no ofrece `image`) como el listado (que ya no debe
    leer `Product.image` directo, sino `primary_image`)."""

    def test_el_formulario_de_producto_ya_no_incluye_el_campo_image(self):
        response = self.client.get(reverse('admin_product_new'))
        self.assertNotIn('image', response.context['form'].fields)

    def test_el_listado_usa_la_galeria_cuando_existe(self):
        producto = Product.objects.create(
            name='Producto con galeria', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0, image='products/legacy-no-usar.jpg',
        )
        ProductMedia.objects.create(product=producto, image=_imagen(), is_primary=True)

        response = self.client.get(reverse('admin_products'))
        self.assertNotContains(response, 'legacy-no-usar.jpg')

    def test_backfill_de_migracion_crea_media_desde_la_imagen_heredada(self):
        import importlib

        from django.apps import apps as real_apps

        migracion = importlib.import_module(
            'products.migrations.0013_backfill_media_from_legacy_image',
        )

        producto = Product.objects.create(
            name='Producto solo con imagen heredada', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0, image=_imagen(),
        )
        self.assertEqual(producto.media.count(), 0)

        migracion.backfill_media(real_apps, None)

        producto.refresh_from_db()
        self.assertEqual(producto.media.count(), 1)
        media = producto.media.first()
        self.assertTrue(media.is_primary)
        self.assertEqual(media.image.name, producto.image.name)

    def test_backfill_no_duplica_si_ya_hay_galeria(self):
        import importlib

        from django.apps import apps as real_apps

        migracion = importlib.import_module(
            'products.migrations.0013_backfill_media_from_legacy_image',
        )
        producto = Product.objects.create(
            name='Producto con imagen y galeria', category=self.categoria, brand=self.marca,
            base_price=Decimal('90000.0000'), stock=0, image=_imagen(),
        )
        ProductMedia.objects.create(product=producto, image=_imagen(), is_primary=True)

        migracion.backfill_media(real_apps, None)

        self.assertEqual(producto.media.count(), 1)


class TallaColorDuplicadoTests(CatalogAdminTestCase):
    """El SKU ya no es un campo que el admin escriba (se genera solo a
    partir de producto+talla+color), asi que lo que antes se validaba como
    "SKU repetido" ahora se valida directamente sobre la combinacion
    talla/color: no puede haber dos variantes iguales para el mismo
    producto, esten en el mismo envio o ya guardadas de antes."""

    def setUp(self):
        super().setUp()
        self.producto = Product.objects.create(
            name='Producto talla color', category=self.categoria, brand=self.marca,
            base_price=Decimal('70000.0000'), stock=0,
        )
        self.existente = ProductVariant.objects.create(
            product=self.producto, sku=build_sku(self.producto.pk, 'S', 'negro'), size='S', color='negro',
        )
        Inventory.objects.create(variant=self.existente, quantity_available=5)

    def test_no_se_puede_repetir_talla_y_color_dentro_del_mismo_envio(self):
        data = {
            'name': self.producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '70000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-id': str(self.existente.pk),
            'variants-0-size': 'S',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '5',
            'variants-1-size': 'M',
            'variants-1-color': 'negro',
            'variants-1-price_override': '',
            'variants-1-is_active': 'on',
            'variants-1-quantity_available': '5',
            'variants-2-size': 'M',
            'variants-2-color': 'negro',
            'variants-2-price_override': '',
            'variants-2-is_active': 'on',
            'variants-2-quantity_available': '5',
            **self._formset_management(total=3, initial=1),
        }
        response = self.client.post(reverse('admin_product_edit', args=[self.producto.pk]), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.producto.variants.filter(size='M', color='negro').count(), 0)

    def test_no_se_puede_crear_una_nueva_variante_igual_a_una_ya_guardada(self):
        data = {
            'name': self.producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '70000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-id': str(self.existente.pk),
            'variants-0-size': 'S',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '5',
            'variants-1-size': 'S',
            'variants-1-color': 'negro',
            'variants-1-price_override': '',
            'variants-1-is_active': 'on',
            'variants-1-quantity_available': '9',
            **self._formset_management(total=2, initial=1),
        }
        response = self.client.post(reverse('admin_product_edit', args=[self.producto.pk]), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.producto.variants.filter(size='S', color='negro').count(), 1)

    def test_editar_la_variante_existente_sin_cambiar_talla_color_no_choca_consigo_misma(self):
        data = {
            'name': self.producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '70000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-id': str(self.existente.pk),
            'variants-0-size': 'S',
            'variants-0-color': 'negro',
            'variants-0-price_override': '',
            'variants-0-is_active': 'on',
            'variants-0-quantity_available': '12',
            **self._formset_management(total=1, initial=1),
        }
        response = self.client.post(reverse('admin_product_edit', args=[self.producto.pk]), data)

        self.assertRedirects(response, reverse('admin_product_edit', args=[self.producto.pk]))
        self.assertEqual(Inventory.objects.get(variant=self.existente).quantity_available, 12)


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
