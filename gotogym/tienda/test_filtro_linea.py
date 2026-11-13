"""Filtro de linea (dama / caballero) del listado de la tienda."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant


def _crear_producto(nombre, talla, sku):
    categoria, _ = ProductCategory.objects.get_or_create(name='Prendas')
    marca, _ = Brand.objects.get_or_create(name='Marca')
    producto = Product.objects.create(
        name=nombre, category=categoria, brand=marca, base_price=Decimal('100000.0000'),
    )
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=talla, color='negro')
    Inventory.objects.create(variant=variante, quantity_available=3)
    return producto


class FiltroDeLineaTests(TestCase):
    def setUp(self):
        # La base de pruebas trae el catalogo semilla de las migraciones; sin
        # variantes activas sus productos no salen en el listado.
        ProductVariant.objects.update(is_active=False)
        self.dama = _crear_producto('Top para dama', 'M', 'LIN-001')
        self.caballero = _crear_producto('Chaqueta para caballero', 'L', 'LIN-002')
        self.unisex = _crear_producto('Gorra unisex', 'UNICA', 'LIN-003')
        self.sin_linea = _crear_producto('Botella deportiva', 'UNICA', 'LIN-004')

    def _nombres(self, **parametros):
        respuesta = self.client.get(reverse('tienda:producto_list'), parametros)
        self.assertEqual(respuesta.status_code, 200)
        return {tarjeta['product'].name for tarjeta in respuesta.context['cards']}

    def test_sin_filtro_se_ve_todo_el_catalogo(self):
        self.assertEqual(
            self._nombres(),
            {'Top para dama', 'Chaqueta para caballero', 'Gorra unisex', 'Botella deportiva'},
        )

    def test_caballero_muestra_caballero_y_unisex(self):
        self.assertEqual(self._nombres(linea='caballero'), {'Chaqueta para caballero', 'Gorra unisex'})

    def test_dama_muestra_dama_y_unisex(self):
        self.assertEqual(self._nombres(linea='dama'), {'Top para dama', 'Gorra unisex'})

    def test_un_valor_desconocido_se_ignora(self):
        respuesta = self.client.get(reverse('tienda:producto_list'), {'linea': 'otra'})
        self.assertEqual(respuesta.context['selected_line'], '')
        self.assertEqual(len(respuesta.context['cards']), 4)

    def test_el_filtro_activo_se_muestra_y_se_puede_quitar(self):
        respuesta = self.client.get(reverse('tienda:producto_list'), {'linea': 'dama'})
        self.assertTrue(respuesta.context['filtros_activos'])
        self.assertContains(respuesta, 'name="linea" value="dama" checked')
        self.assertEqual(str(respuesta.context['selected_line_name']), 'Dama')
