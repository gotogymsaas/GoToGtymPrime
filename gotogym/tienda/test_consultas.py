"""Consultas a la base por pagina: portada, listado y ficha.

Los interruptores del panel se leen una sola vez por pagina (antes cada
procesador de contexto hacia su propia consulta) y el listado no hace mas
consultas cuando hay mas productos, lo que delata una consulta dentro de un
bucle de plantilla.
"""
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant


def _consultas_a_ajustes(captura):
    return [q for q in captura.captured_queries if 'administracion_panelsettings' in q['sql']]


class ConsultasPorPaginaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria consultas')
        marca = Brand.objects.create(name='Marca consultas')
        cls.productos = []
        for n in range(3):
            producto = Product.objects.create(
                name=f'Producto consultas {n}', category=categoria, brand=marca,
                base_price=Decimal('100000.0000'), stock=0,
            )
            variante = ProductVariant.objects.create(
                product=producto, sku=f'CONS-{n}-S-NEG', size='S', color='negro',
            )
            Inventory.objects.create(variant=variante, quantity_available=5)
            cls.productos.append(producto)

    def _consultas(self, url):
        with CaptureQueriesContext(connection) as captura:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return captura

    def test_la_portada_lee_los_interruptores_una_vez(self):
        captura = self._consultas(reverse('home'))
        self.assertEqual(len(_consultas_a_ajustes(captura)), 1)

    def test_el_listado_lee_los_interruptores_una_vez(self):
        captura = self._consultas(reverse('tienda:producto_list'))
        self.assertEqual(len(_consultas_a_ajustes(captura)), 1)

    def test_la_ficha_lee_los_interruptores_una_vez(self):
        captura = self._consultas(reverse('tienda:producto_detail', args=[self.productos[0].pk]))
        self.assertEqual(len(_consultas_a_ajustes(captura)), 1)

    def test_el_listado_no_crece_con_el_numero_de_productos(self):
        base = len(self._consultas(reverse('tienda:producto_list')).captured_queries)
        categoria = ProductCategory.objects.get(name='Categoria consultas')
        marca = Brand.objects.get(name='Marca consultas')
        for n in range(3, 8):
            producto = Product.objects.create(
                name=f'Producto consultas {n}', category=categoria, brand=marca,
                base_price=Decimal('100000.0000'), stock=0,
            )
            variante = ProductVariant.objects.create(
                product=producto, sku=f'CONS-{n}-S-NEG', size='S', color='negro',
            )
            Inventory.objects.create(variant=variante, quantity_available=5)

        despues = len(self._consultas(reverse('tienda:producto_list')).captured_queries)

        self.assertEqual(despues, base)
