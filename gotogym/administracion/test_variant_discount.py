"""Descuento por variante: modelo, formulario del panel y lo que ve el
comprador (tarjeta, ficha, carrito)."""
from decimal import Decimal

from carrito.services import CART_VERSION, build_cart_context
from django.urls import reverse
from inventory.models import Inventory
from products.models import ProductVariant
from tienda.catalog import build_product_card, catalog_variants_queryset

from .test_catalog_admin import CatalogAdminTestCase, Product


class DescuentoDeVarianteBase(CatalogAdminTestCase):
    def setUp(self):
        super().setUp()
        self.producto = Product.objects.create(
            name='Producto con descuento', category=self.categoria, brand=self.marca,
            base_price=Decimal('100000.0000'), stock=0,
        )
        self.variante = ProductVariant.objects.create(
            product=self.producto, sku='DESC-001', size='M', color='negro',
        )
        Inventory.objects.create(variant=self.variante, quantity_available=5)

    def _post_variante(self, **campos):
        data = {
            'name': self.producto.name, 'category': self.categoria.pk, 'brand': self.marca.pk,
            'description': '', 'base_price': '100000', 'discount': '0', 'stock': '0', 'featured': '',
            'variants-0-id': str(self.variante.pk),
            'variants-0-size': 'M', 'variants-0-color': 'negro',
            'variants-0-price_override': '', 'variants-0-discount_price': '',
            'variants-0-discount_percent': '',
            'variants-0-is_active': 'on', 'variants-0-quantity_available': '5',
            **self._formset_management(total=1, initial=1),
        }
        data.update({f'variants-0-{clave}': valor for clave, valor in campos.items()})
        return self.client.post(reverse('admin_product_edit', args=[self.producto.pk]), data)


class ModeloTests(DescuentoDeVarianteBase):
    def test_sin_descuento_cobra_el_precio_normal(self):
        self.assertFalse(self.variante.has_discount)
        self.assertEqual(self.variante.effective_price, Decimal('100000'))
        self.assertEqual(self.variante.discount_percent, 0)

    def test_con_descuento_cobra_el_vigente_y_conserva_el_normal(self):
        self.variante.discount_price = Decimal('80000')
        self.assertTrue(self.variante.has_discount)
        self.assertEqual(self.variante.effective_price, Decimal('80000'))
        self.assertEqual(self.variante.list_price, Decimal('100000'))
        self.assertEqual(self.variante.discount_percent, 20)

    def test_el_descuento_parte_del_precio_propio_si_existe(self):
        self.variante.price_override = Decimal('120000')
        self.variante.discount_price = Decimal('90000')
        self.assertEqual(self.variante.list_price, Decimal('120000'))
        self.assertEqual(self.variante.discount_percent, 25)

    def test_un_descuento_igual_o_mayor_al_normal_se_ignora(self):
        for valor in (Decimal('100000'), Decimal('150000'), Decimal('0')):
            self.variante.discount_price = valor
            self.assertFalse(self.variante.has_discount, valor)
            self.assertEqual(self.variante.effective_price, Decimal('100000'), valor)


class FormularioDelPanelTests(DescuentoDeVarianteBase):
    def test_guarda_el_precio_con_descuento(self):
        self._post_variante(discount_price='80.000')
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.discount_price, Decimal('80000'))

    def test_el_porcentaje_se_convierte_en_precio_a_pagar(self):
        self._post_variante(discount_percent='25')
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.discount_price, Decimal('75000'))
        self.assertEqual(self.variante.discount_percent, 25)

    def test_el_porcentaje_usa_el_precio_propio_de_la_variante(self):
        self._post_variante(price_override='120.000', discount_percent='50')
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.discount_price, Decimal('60000'))

    def test_precio_con_descuento_no_puede_ser_mayor_o_igual_al_normal(self):
        respuesta = self._post_variante(discount_price='100.000')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'debe ser menor al precio normal')
        self.variante.refresh_from_db()
        self.assertIsNone(self.variante.discount_price)

    def test_no_acepta_precio_y_porcentaje_tocados_a_la_vez(self):
        respuesta = self._post_variante(discount_price='80.000', discount_percent='10')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no los dos')
        self.variante.refresh_from_db()
        self.assertIsNone(self.variante.discount_price)

    def test_un_porcentaje_nuevo_reemplaza_el_precio_ya_guardado_sin_tocar(self):
        self.variante.discount_price = Decimal('80000')
        self.variante.save()
        # El formulario reenvia el precio guardado tal cual; solo se escribe
        # el porcentaje.
        self._post_variante(discount_price='80.000', discount_percent='40')
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.discount_price, Decimal('60000'))

    def test_vaciar_el_precio_quita_el_descuento(self):
        self.variante.discount_price = Decimal('80000')
        self.variante.save()
        self._post_variante(discount_price='')
        self.variante.refresh_from_db()
        self.assertIsNone(self.variante.discount_price)


class VisualizacionTests(DescuentoDeVarianteBase):
    def setUp(self):
        super().setUp()
        self.variante.discount_price = Decimal('80000')
        self.variante.save()
        self.client.logout()

    def test_la_tarjeta_trae_precio_vigente_y_el_normal_para_tachar(self):
        producto = Product.objects.prefetch_related('variants').get(pk=self.producto.pk)
        tarjeta = build_product_card(producto)
        self.assertEqual(tarjeta['price_min'], Decimal('80000'))
        self.assertEqual(tarjeta['compare_price'], Decimal('100000'))
        self.assertEqual(tarjeta['discount_percent'], 20)

    def test_la_tarjeta_sin_descuento_no_trae_precio_tachado(self):
        self.variante.discount_price = None
        self.variante.save()
        producto = Product.objects.prefetch_related('variants').get(pk=self.producto.pk)
        self.assertIsNone(build_product_card(producto)['compare_price'])

    def test_el_listado_muestra_el_precio_normal_tachado_y_el_vigente(self):
        html = self.client.get(reverse('tienda:producto_list')).content.decode()
        self.assertIn('<s class="price-compare">$100.000</s>', html)
        self.assertIn('$80.000 COP', html)
        self.assertIn('-20%', html)

    def test_la_ficha_muestra_el_descuento_y_lo_entrega_al_script(self):
        respuesta = self.client.get(reverse('tienda:producto_detail', args=[self.producto.pk]))
        self.assertContains(respuesta, '<s class="price-compare">$100.000</s>')
        variantes = respuesta.context['variantes_json']
        self.assertEqual(variantes[0]['price'], 80000.0)
        self.assertEqual(variantes[0]['list_price'], 100000.0)
        self.assertTrue(variantes[0]['has_discount'])
        self.assertEqual(variantes[0]['discount_percent'], 20)

    def test_la_consulta_de_variante_informa_el_descuento(self):
        respuesta = self.client.get(
            reverse('tienda:producto_variante', args=[self.producto.pk]),
            {'size': 'M', 'color': 'negro'},
        )
        datos = respuesta.json()
        self.assertEqual(datos['price'], 80000.0)
        self.assertEqual(datos['list_price'], 100000.0)
        self.assertTrue(datos['has_discount'])

    def test_el_producto_sin_descuento_se_ve_como_antes(self):
        self.variante.discount_price = None
        self.variante.save()
        html = self.client.get(reverse('tienda:producto_list')).content.decode()
        self.assertNotIn('price-compare', html)
        self.assertIn('$100.000 COP', html)

    def test_el_carrito_cobra_el_precio_con_descuento(self):
        cart = {str(self.variante.pk): 2}
        contexto = build_cart_context(cart)
        self.assertEqual(contexto['subtotal'], Decimal('160000'))
        self.assertEqual(contexto['items'][0]['precio_lista'], Decimal('100000'))

        session = self.client.session
        session['cart'] = cart
        session['cart_version'] = CART_VERSION
        session.save()
        html = self.client.get(reverse('carrito:cart_detail')).content.decode()
        self.assertIn('<s class="price-compare">$100.000</s>', html)

    def test_catalogo_lee_las_variantes_con_el_descuento(self):
        variante = catalog_variants_queryset().get(pk=self.variante.pk)
        self.assertEqual(variante.effective_price, Decimal('80000'))
