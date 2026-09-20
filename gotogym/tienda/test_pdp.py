"""Ficha de producto: seleccion de variante, disponibilidad real y validacion."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant


def _crear_producto(nombre, categoria, marca, precio='100000.0000'):
    return Product.objects.create(
        name=nombre, category=categoria, brand=marca,
        base_price=Decimal(precio), stock=0,
    )


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class TiendaAutenticadaMixin:
    def setUp(self):
        super().setUp()
        User = get_user_model()
        correo = f'pdp-{self._testMethodName[:30]}@example.com'
        usuario = User.objects.create_user(email=correo, username=correo, password='secret123')
        self.client.force_login(usuario)


class FichaDeProductoTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria PDP')
        cls.marca = Brand.objects.create(name='Marca PDP')

        cls.multi = _crear_producto('Producto PDP multivariante', cls.categoria, cls.marca, '150000.0000')
        cls.v_s_negro = _crear_variante(cls.multi, 'PDP-001-S-NEG', 'S', 'negro', 4)
        cls.v_l_negro = _crear_variante(cls.multi, 'PDP-001-L-NEG', 'L', 'negro', 0)

        cls.unico = _crear_producto('Producto PDP variante unica', cls.categoria, cls.marca, '99000.0000')
        cls.v_unica = _crear_variante(cls.unico, 'PDP-002-U-UNI', 'UNICA', 'UNICO', 3)

        cls.agotado = _crear_producto('Producto PDP agotado', cls.categoria, cls.marca, '70000.0000')
        cls.v_agotada = _crear_variante(cls.agotado, 'PDP-003-S-NEG', 'S', 'negro', 0)

    def _url(self, producto):
        return reverse('tienda:producto_detail', args=[producto.pk])

    def test_la_ficha_expone_las_variantes_reales(self):
        response = self.client.get(self._url(self.multi))
        self.assertEqual(response.status_code, 200)
        skus = sorted(v['sku'] for v in response.context['variantes'])
        self.assertEqual(skus, ['PDP-001-L-NEG', 'PDP-001-S-NEG'])

    def test_marca_disponibilidad_por_variante(self):
        response = self.client.get(self._url(self.multi))
        por_sku = {v['sku']: v for v in response.context['variantes']}
        self.assertTrue(por_sku['PDP-001-S-NEG']['available'])
        self.assertFalse(por_sku['PDP-001-L-NEG']['available'])

    def test_producto_de_variante_unica_la_preselecciona(self):
        response = self.client.get(self._url(self.unico))
        self.assertIsNotNone(response.context['single_variant'])
        self.assertContains(response, 'value="{}"'.format(self.v_unica.id))

    def test_producto_de_variante_unica_no_pinta_selectores(self):
        response = self.client.get(self._url(self.unico))
        self.assertNotContains(response, 'class="pdp-size')
        self.assertNotContains(response, 'class="pdp-color')

    def test_producto_agotado_deshabilita_el_boton(self):
        response = self.client.get(self._url(self.agotado))
        self.assertFalse(response.context['in_stock'])
        self.assertContains(response, 'disabled')

    def test_no_muestra_datos_simulados(self):
        response = self.client.get(self._url(self.multi))
        contenido = response.content.decode()
        self.assertNotIn('reviews_count', contenido)
        self.assertNotIn('old_price', contenido)
        self.assertNotIn('long_description', contenido)
        self.assertNotIn('>star<', contenido)

    def test_muestra_placeholder_neutro_de_resenas(self):
        response = self.client.get(self._url(self.multi))
        self.assertContains(response, 'Sin rese')

    def test_no_queda_el_boton_comprar_ahora(self):
        response = self.client.get(self._url(self.multi))
        self.assertNotContains(response, 'Comprar ahora')


class EndpointDeVarianteTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria endpoint')
        cls.marca = Brand.objects.create(name='Marca endpoint')
        cls.producto = _crear_producto('Producto endpoint', cls.categoria, cls.marca, '110000.0000')
        cls.disponible = _crear_variante(cls.producto, 'END-001-S-NEG', 'S', 'negro', 2)
        cls.sin_stock = _crear_variante(cls.producto, 'END-001-M-NEG', 'M', 'negro', 0)

    def _url(self):
        return reverse('tienda:producto_variante', args=[self.producto.pk])

    def test_devuelve_datos_de_la_combinacion(self):
        response = self.client.get(self._url(), {'size': 'S', 'color': 'negro'})
        self.assertEqual(response.status_code, 200)
        datos = response.json()
        self.assertEqual(datos['sku'], 'END-001-S-NEG')
        self.assertEqual(datos['variant_id'], self.disponible.id)
        self.assertTrue(datos['available'])
        self.assertEqual(datos['stock'], 2)

    def test_available_false_cuando_no_hay_unidades(self):
        response = self.client.get(self._url(), {'size': 'M', 'color': 'negro'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['available'])

    def test_combinacion_inexistente_devuelve_404(self):
        response = self.client.get(self._url(), {'size': 'XXL', 'color': 'negro'})
        self.assertEqual(response.status_code, 404)

    def test_sin_parametros_devuelve_404(self):
        self.assertEqual(self.client.get(self._url()).status_code, 404)


class AgregarAlCarritoDesdeLaFichaTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria add')
        cls.marca = Brand.objects.create(name='Marca add')

        cls.producto = _crear_producto('Producto add', cls.categoria, cls.marca)
        cls.v_ok = _crear_variante(cls.producto, 'ADD-001-S-NEG', 'S', 'negro', 3)
        cls.v_sin_stock = _crear_variante(cls.producto, 'ADD-001-L-NEG', 'L', 'negro', 0)

    def _url(self, variante):
        return reverse('carrito:add_to_cart', args=[variante.pk])

    def test_variante_con_stock_se_agrega(self):
        response = self.client.post(self._url(self.v_ok))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['cart'], {str(self.v_ok.pk): 1})

    def test_variante_sin_stock_se_rechaza(self):
        response = self.client.post(self._url(self.v_sin_stock))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('cart', {}), {})

    def test_variante_inexistente_devuelve_404(self):
        response = self.client.post(reverse('carrito:add_to_cart', args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_no_se_puede_superar_el_stock_disponible(self):
        for _ in range(3):
            self.client.post(self._url(self.v_ok))
        self.assertEqual(self.client.session['cart'], {str(self.v_ok.pk): 3})

        # La cuarta unidad excede el inventario y no debe modificar el carrito.
        self.client.post(self._url(self.v_ok))
        self.assertEqual(self.client.session['cart'], {str(self.v_ok.pk): 3})

    def test_peticion_ajax_sin_stock_devuelve_400(self):
        response = self.client.post(
            self._url(self.v_sin_stock), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
