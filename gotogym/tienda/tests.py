"""Listado de catalogo: filtros por disponibilidad real, precios y paginacion."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant


def _crear_producto(nombre, categoria, marca, precio='100000.0000', imagen=''):
    return Product.objects.create(
        name=nombre, category=categoria, brand=marca,
        base_price=Decimal(precio), stock=0, image=imagen,
    )


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class TiendaAutenticadaMixin:
    """Store exige sesion iniciada, asi que los tests de catalogo parten de
    un usuario autenticado."""

    def setUp(self):
        super().setUp()
        User = get_user_model()
        correo = f'plp-{self._testMethodName[:30]}@example.com'
        usuario = User.objects.create_user(email=correo, username=correo, password='secret123')
        self.client.force_login(usuario)


class CatalogoBaseTestCase(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria_a = ProductCategory.objects.create(name='Categoria PLP A')
        cls.categoria_b = ProductCategory.objects.create(name='Categoria PLP B')
        cls.marca = Brand.objects.create(name='Marca PLP')

        # Con stock en S/negro y M/azul
        cls.con_stock = _crear_producto('Legging PLP con stock', cls.categoria_a, cls.marca, '120000.0000')
        _crear_variante(cls.con_stock, 'PLP-001-S-NEG', 'S', 'negro', 5)
        _crear_variante(cls.con_stock, 'PLP-001-M-AZU', 'M', 'azul', 3)

        # Variante en talla S pero sin unidades
        cls.agotado = _crear_producto('Camiseta PLP agotada', cls.categoria_a, cls.marca, '80000.0000')
        _crear_variante(cls.agotado, 'PLP-002-S-NEG', 'S', 'negro', 0)

        # Otra categoria, precio mas alto
        cls.otra_categoria = _crear_producto('Chaqueta PLP otra', cls.categoria_b, cls.marca, '300000.0000')
        _crear_variante(cls.otra_categoria, 'PLP-003-L-VER', 'L', 'verde', 2)

    def _nombres(self, response):
        return [card['product'].name for card in response.context['cards']]


class ListadoVisibleTests(CatalogoBaseTestCase):
    def test_el_catalogo_completo_se_ve_sin_elegir_categoria(self):
        response = self.client.get(reverse('tienda:producto_list'))
        self.assertEqual(response.status_code, 200)
        nombres = self._nombres(response)
        self.assertIn(self.con_stock.name, nombres)
        self.assertIn(self.otra_categoria.name, nombres)

    def test_no_quedan_selects_que_oculten_el_listado(self):
        response = self.client.get(reverse('tienda:producto_list'))
        self.assertNotContains(response, 'storeProductSelect')
        self.assertNotContains(response, 'storeProductList')

    def test_producto_sin_stock_se_marca_como_agotado(self):
        response = self.client.get(reverse('tienda:producto_list'))
        card = next(c for c in response.context['cards'] if c['product'].pk == self.agotado.pk)
        self.assertFalse(card['in_stock'])
        self.assertContains(response, 'Agotado')

    def test_la_tarjeta_expone_tallas_y_colores_con_stock(self):
        response = self.client.get(reverse('tienda:producto_list'))
        card = next(c for c in response.context['cards'] if c['product'].pk == self.con_stock.pk)
        self.assertEqual(card['sizes'], ['S', 'M'])
        self.assertEqual(card['colors'], ['azul', 'negro'])

    def test_la_tarjeta_de_un_producto_agotado_no_lista_tallas_disponibles(self):
        response = self.client.get(reverse('tienda:producto_list'))
        card = next(c for c in response.context['cards'] if c['product'].pk == self.agotado.pk)
        self.assertEqual(card['sizes'], [])


class FiltrosTests(CatalogoBaseTestCase):
    def test_filtro_por_talla_solo_devuelve_productos_con_esa_talla_disponible(self):
        response = self.client.get(reverse('tienda:producto_list'), {'talla': 'S'})
        nombres = self._nombres(response)
        self.assertIn(self.con_stock.name, nombres)
        # Tiene talla S, pero con inventario en cero: no debe aparecer.
        self.assertNotIn(self.agotado.name, nombres)

    def test_filtro_por_color_usa_disponibilidad_real(self):
        response = self.client.get(reverse('tienda:producto_list'), {'color': 'negro'})
        nombres = self._nombres(response)
        self.assertIn(self.con_stock.name, nombres)
        self.assertNotIn(self.agotado.name, nombres)

    def test_filtro_por_categoria_sigue_funcionando(self):
        response = self.client.get(reverse('tienda:producto_list'), {'categoria': self.categoria_b.id})
        self.assertEqual(self._nombres(response), [self.otra_categoria.name])

    def test_filtro_por_rango_de_precio(self):
        # Acotado por arriba para aislar el producto de este test del catalogo
        # semilla, cuyos precios estan por encima de 320000.
        response = self.client.get(
            reverse('tienda:producto_list'), {'precio_min': '200000', 'precio_max': '320000'}
        )
        self.assertEqual(self._nombres(response), [self.otra_categoria.name])

    def test_busqueda_por_nombre(self):
        response = self.client.get(reverse('tienda:producto_list'), {'filtro': 'Chaqueta PLP'})
        self.assertEqual(self._nombres(response), [self.otra_categoria.name])

    def test_orden_por_precio_ascendente(self):
        response = self.client.get(reverse('tienda:producto_list'), {'orden': 'precio_asc'})
        precios = [card['product'].base_price for card in response.context['cards']]
        self.assertEqual(precios, sorted(precios))

    def test_combinacion_de_filtros_sin_resultados_no_rompe(self):
        response = self.client.get(reverse('tienda:producto_list'), {'talla': 'S', 'color': 'verde'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._nombres(response), [])

    def test_talla_inexistente_devuelve_listado_vacio(self):
        response = self.client.get(reverse('tienda:producto_list'), {'talla': 'XXL'})
        self.assertEqual(self._nombres(response), [])

    def test_parametro_desconocido_se_ignora(self):
        response = self.client.get(reverse('tienda:producto_list'), {'rating': '5'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['cards'])


class PaginacionTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria paginacion')
        marca = Brand.objects.create(name='Marca paginacion')
        for i in range(15):
            producto = _crear_producto(f'Producto paginado {i:02d}', categoria, marca)
            _crear_variante(producto, f'PAG-{i:03d}-S-NEG', 'S', 'negro', 1)

    def test_la_primera_pagina_limita_los_resultados(self):
        response = self.client.get(reverse('tienda:producto_list'))
        self.assertEqual(len(response.context['cards']), 12)
        self.assertTrue(response.context['page_obj'].has_next())

    def test_la_segunda_pagina_trae_el_resto(self):
        response = self.client.get(reverse('tienda:producto_list'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['page_obj'].has_next())


class PrecioDeTarjetaTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria precios')
        cls.marca = Brand.objects.create(name='Marca precios')

    def test_precio_unico_cuando_no_hay_override(self):
        producto = _crear_producto('Precio plano', self.categoria, self.marca, '90000.0000')
        _crear_variante(producto, 'PRE-001-S-NEG', 'S', 'negro', 1)

        response = self.client.get(reverse('tienda:producto_list'))
        card = next(c for c in response.context['cards'] if c['product'].pk == producto.pk)
        self.assertFalse(card['has_price_range'])
        self.assertEqual(card['price_min'], Decimal('90000.0000'))

    def test_rango_de_precio_cuando_una_variante_tiene_precio_propio(self):
        producto = _crear_producto('Precio variable', self.categoria, self.marca, '90000.0000')
        _crear_variante(producto, 'PRE-002-S-NEG', 'S', 'negro', 1)
        variante = _crear_variante(producto, 'PRE-002-L-NEG', 'L', 'negro', 1)
        variante.price_override = Decimal('130000.0000')
        variante.save(update_fields=['price_override'])

        response = self.client.get(reverse('tienda:producto_list'))
        card = next(c for c in response.context['cards'] if c['product'].pk == producto.pk)
        self.assertTrue(card['has_price_range'])
        self.assertEqual(card['price_min'], Decimal('90000.0000'))
        self.assertEqual(card['price_max'], Decimal('130000.0000'))


class ImagenDeTarjetaTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria imagenes')
        cls.marca = Brand.objects.create(name='Marca imagenes')

    def test_usa_la_media_marcada_como_principal(self):
        producto = _crear_producto('Con media', self.categoria, self.marca, imagen='products/vieja.jpg')
        _crear_variante(producto, 'IMG-001-S-NEG', 'S', 'negro', 1)
        ProductMedia.objects.create(product=producto, image='products/secundaria.jpg', sort_order=2)
        ProductMedia.objects.create(product=producto, image='products/principal.jpg', is_primary=True)

        response = self.client.get(reverse('tienda:producto_list'))
        card = next(c for c in response.context['cards'] if c['product'].pk == producto.pk)
        self.assertEqual(card['image'].name, 'products/principal.jpg')

    def test_cae_a_la_imagen_del_producto_si_no_hay_media(self):
        producto = _crear_producto('Sin media', self.categoria, self.marca, imagen='products/heredada.jpg')
        _crear_variante(producto, 'IMG-002-S-NEG', 'S', 'negro', 1)

        response = self.client.get(reverse('tienda:producto_list'))
        card = next(c for c in response.context['cards'] if c['product'].pk == producto.pk)
        self.assertEqual(card['image'].name, 'products/heredada.jpg')

    def test_producto_sin_ninguna_imagen_no_rompe_el_listado(self):
        producto = _crear_producto('Sin imagen alguna', self.categoria, self.marca)
        _crear_variante(producto, 'IMG-003-S-NEG', 'S', 'negro', 1)

        response = self.client.get(reverse('tienda:producto_list'))
        self.assertEqual(response.status_code, 200)
        card = next(c for c in response.context['cards'] if c['product'].pk == producto.pk)
        self.assertIsNone(card['image'])
        self.assertContains(response, 'placeholder.webp')
