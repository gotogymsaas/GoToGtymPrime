"""Carrito: metodo HTTP exigido, disponibilidad, totales y acceso."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

from .services import CART_VERSION, build_cart_context


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class CarritoAutenticadoMixin:
    def setUp(self):
        super().setUp()
        User = get_user_model()
        correo = f'carrito-{self._testMethodName[:30]}@example.com'
        self.usuario = User.objects.create_user(
            email=correo, username=correo, password='secret123',
        )
        self.client.force_login(self.usuario)

    def _poner_en_carrito(self, mapa):
        session = self.client.session
        session['cart'] = mapa
        session['cart_version'] = CART_VERSION
        session.save()


class CartMutationsRequirePostTests(CarritoAutenticadoMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        category = ProductCategory.objects.create(name='Categoria carrito test')
        brand = Brand.objects.create(name='Marca carrito test')
        cls.product = Product.objects.create(
            name='Producto de prueba carrito', category=category, brand=brand,
            base_price=Decimal('100000.0000'), stock=10,
        )
        cls.variant = _crear_variante(cls.product, 'CART-TEST-U-UNI', 'UNICA', 'UNICO', 10)

    def test_add_to_cart_via_get_is_not_allowed(self):
        response = self.client.get(reverse('carrito:add_to_cart', args=[self.variant.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session.get('cart', {}), {})

    def test_update_cart_via_get_is_not_allowed(self):
        self._poner_en_carrito({str(self.variant.pk): 1})
        response = self.client.get(
            reverse('carrito:update_cart', args=[self.variant.pk]), {'cantidad': 5}
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session['cart'], {str(self.variant.pk): 1})

    def test_remove_from_cart_via_get_is_not_allowed(self):
        self._poner_en_carrito({str(self.variant.pk): 1})
        response = self.client.get(reverse('carrito:remove_from_cart', args=[self.variant.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session['cart'], {str(self.variant.pk): 1})

    def test_add_to_cart_via_post_still_works(self):
        response = self.client.post(reverse('carrito:add_to_cart', args=[self.variant.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['cart'], {str(self.variant.pk): 1})

    def test_add_to_cart_ajax_returns_json_cart_count(self):
        response = self.client.post(
            reverse('carrito:add_to_cart', args=[self.variant.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True, 'cart_count': 1})

    def test_remove_vacia_la_linea(self):
        self._poner_en_carrito({str(self.variant.pk): 2})
        self.client.post(reverse('carrito:remove_from_cart', args=[self.variant.pk]))
        self.assertEqual(self.client.session['cart'], {})

    def test_update_a_cero_elimina_la_linea(self):
        self._poner_en_carrito({str(self.variant.pk): 2})
        self.client.post(reverse('carrito:update_cart', args=[self.variant.pk]), {'cantidad': 0})
        self.assertEqual(self.client.session['cart'], {})


class DisponibilidadDelCarritoTests(CarritoAutenticadoMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        category = ProductCategory.objects.create(name='Categoria disponibilidad')
        brand = Brand.objects.create(name='Marca disponibilidad')
        cls.product = Product.objects.create(
            name='Producto disponibilidad', category=category, brand=brand,
            base_price=Decimal('50000.0000'), stock=2,
        )
        cls.variant = _crear_variante(cls.product, 'DISP-001-S-NEG', 'S', 'negro', 2)

    def test_no_se_puede_agregar_mas_de_lo_disponible(self):
        self._poner_en_carrito({str(self.variant.pk): 2})
        response = self.client.post(reverse('carrito:add_to_cart', args=[self.variant.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['cart'], {str(self.variant.pk): 2})

    def test_update_por_encima_del_stock_se_rechaza(self):
        self._poner_en_carrito({str(self.variant.pk): 1})
        self.client.post(reverse('carrito:update_cart', args=[self.variant.pk]), {'cantidad': 99})
        self.assertEqual(self.client.session['cart'], {str(self.variant.pk): 1})

    def test_update_dentro_del_stock_se_acepta(self):
        self._poner_en_carrito({str(self.variant.pk): 1})
        self.client.post(reverse('carrito:update_cart', args=[self.variant.pk]), {'cantidad': 2})
        self.assertEqual(self.client.session['cart'], {str(self.variant.pk): 2})


class CartTotalCalculationTests(CarritoAutenticadoMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        category = ProductCategory.objects.create(name='Categoria totales test')
        brand = Brand.objects.create(name='Marca totales test')
        cls.product_a = Product.objects.create(
            name='Producto A', category=category, brand=brand,
            base_price=Decimal('100000.0000'), stock=10, image='products/test_producto_a.jpg',
        )
        cls.variant_a = _crear_variante(cls.product_a, 'TOT-001-S-NEG', 'S', 'negro', 10)
        cls.product_b = Product.objects.create(
            name='Producto B', category=category, brand=brand,
            base_price=Decimal('50000.0000'), stock=10,
        )
        cls.variant_b = _crear_variante(cls.product_b, 'TOT-002-M-AZU', 'M', 'azul', 10)

    def test_build_cart_context_matches_expected_sum(self):
        cart = {str(self.variant_a.pk): 2, str(self.variant_b.pk): 3}
        context = build_cart_context(cart)

        esperado = Decimal('100000.0000') * 2 + Decimal('50000.0000') * 3
        self.assertEqual(context['subtotal'], esperado)
        self.assertEqual(context['total'], esperado)
        self.assertEqual(context['num_items'], 5)
        self.assertEqual(len(context['items']), 2)

    def test_carrito_vacio_no_suma_nada(self):
        context = build_cart_context({})
        self.assertEqual(context['subtotal'], Decimal('0'))
        self.assertEqual(context['total'], Decimal('0'))
        self.assertEqual(context['items'], [])

    def test_el_precio_se_recalcula_desde_la_variante(self):
        # Aunque la sesion se manipule, el precio sale de la base de datos.
        self.variant_a.price_override = Decimal('70000.0000')
        self.variant_a.save(update_fields=['price_override'])

        context = build_cart_context({str(self.variant_a.pk): 1})
        self.assertEqual(context['total'], Decimal('70000.0000'))

    def test_una_variante_inexistente_en_sesion_se_ignora(self):
        context = build_cart_context({str(self.variant_a.pk): 1, '999999': 5})
        self.assertEqual(len(context['items']), 1)
        self.assertEqual(context['total'], Decimal('100000.0000'))

    def test_cart_detail_muestra_talla_color_y_sku(self):
        self._poner_en_carrito({str(self.variant_a.pk): 1})
        response = self.client.get(reverse('carrito:cart_detail'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TOT-001-S-NEG')
        self.assertContains(response, 'negro')

    def test_cart_detail_renders_product_without_image(self):
        self._poner_en_carrito({str(self.variant_b.pk): 1})
        response = self.client.get(reverse('carrito:cart_detail'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'placeholder.webp')

    def test_cart_detail_view_uses_centralized_total(self):
        self._poner_en_carrito({str(self.variant_a.pk): 1})
        response = self.client.get(reverse('carrito:cart_detail'))
        esperado = build_cart_context({str(self.variant_a.pk): 1})
        self.assertEqual(response.context['total'], esperado['total'])

    def test_el_carrito_muestra_una_estimacion_de_envio_no_un_numero_fijo(self):
        self._poner_en_carrito({str(self.variant_a.pk): 1})
        response = self.client.get(reverse('carrito:cart_detail'))
        self.assertGreater(response.context['shipping_estimate'], Decimal('0'))
        self.assertContains(response, 'confirma con tu dirección')


class CarritoHeredadoTests(CarritoAutenticadoMixin, TestCase):
    """Un carrito guardado con el formato anterior (claves de producto) no
    puede reinterpretarse como variantes: se descarta."""

    @classmethod
    def setUpTestData(cls):
        category = ProductCategory.objects.create(name='Categoria heredado')
        brand = Brand.objects.create(name='Marca heredado')
        cls.product = Product.objects.create(
            name='Producto heredado', category=category, brand=brand,
            base_price=Decimal('10000.0000'), stock=5,
        )
        cls.variant = _crear_variante(cls.product, 'LEG-001-S-NEG', 'S', 'negro', 5)

    def test_carrito_sin_version_se_reinicia(self):
        session = self.client.session
        session['cart'] = {str(self.product.pk): 3}
        session.save()

        response = self.client.get(reverse('carrito:cart_detail'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['cart'], {})
        self.assertContains(response, 'se reinicio')

    def test_carrito_con_version_actual_se_conserva(self):
        self._poner_en_carrito({str(self.variant.pk): 1})
        self.client.get(reverse('carrito:cart_detail'))
        self.assertEqual(self.client.session['cart'], {str(self.variant.pk): 1})


class AccesoAlCarritoTests(TestCase):
    """Store y carrito exigen sesion iniciada."""

    def test_carrito_anonimo_redirige_a_login_con_next(self):
        response = self.client.get(reverse('carrito:cart_detail'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)

    def test_tienda_anonima_redirige_a_login_con_next(self):
        url = reverse('tienda:producto_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)
        self.assertIn(url, response.url)


class CommerceRegressionTests(TestCase):
    """Login, blog e i18n no deben verse afectados por los cambios del
    carrito y la tienda."""

    def test_login_still_works(self):
        User = get_user_model()
        User.objects.create_user(
            email='cliente-regresion@example.com',
            username='cliente-regresion@example.com',
            password='secret123',
        )
        response = self.client.post(
            reverse('commercial_login'),
            {'username': 'cliente-regresion@example.com', 'password': 'secret123'},
        )
        self.assertEqual(response.status_code, 302)

    def test_blog_list_still_works_under_i18n_prefix(self):
        response = self.client.get('/es/blog/')
        self.assertEqual(response.status_code, 200)
