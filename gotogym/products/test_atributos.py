"""Atributos visuales del catalogo: deduccion desde el nombre y vocabulario cerrado."""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from . import atributos
from .models import Brand, Product, ProductCategory, ProductVariant


class DeduccionTests(SimpleTestCase):
    def test_tipo_de_prenda_del_catalogo_real(self):
        casos = {
            'Leggins gris azulado para dama': 'leggings',
            'Pantalon verde': 'pantalon',
            'Chaqueta naranja + grafeno cremallera caballero': 'chaqueta',
            'Conjunto negro con cuello mao para caballero': 'conjunto',
            'Saco negro gris': 'buzo',
            'Blazer negro para dama': 'blazer',
            'Top ombliguero blanco con estampado hexagonal para dama': 'top',
            'Camiseta blanca con estampado geometrico para caballero': 'camiseta',
            'X5 Generation Mujer': '',
        }
        for nombre, esperado in casos.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(atributos.inferir_tipo(nombre), esperado)

    def test_el_nombre_manda_sobre_la_descripcion(self):
        self.assertEqual(atributos.inferir_tipo('Chaqueta gris', 'Combina con leggins'), 'chaqueta')
        self.assertEqual(atributos.inferir_tipo('X5 Generation', 'Leggins de alta costura'), 'leggings')

    def test_manga_cuello_y_diseno_solo_si_el_texto_lo_dice(self):
        self.assertEqual(atributos.inferir_manga('Camiseta manga larga'), 'larga')
        self.assertEqual(atributos.inferir_manga('Esqueleto deportivo'), 'sin_manga')
        self.assertEqual(atributos.inferir_manga('Camiseta blanca'), '')
        self.assertEqual(atributos.inferir_cuello('Conjunto con cuello mao'), 'mao')
        self.assertEqual(atributos.inferir_cuello('Buzo con capucha'), 'capucha')
        self.assertEqual(atributos.inferir_cuello('Camiseta'), '')
        self.assertEqual(atributos.inferir_diseno('Top con estampado geometrico'), 'estampado')
        self.assertEqual(atributos.inferir_diseno('Chaqueta negra con paneles hexagonales'), 'bloques')

    def test_colores_del_texto_en_orden_y_sin_repetir(self):
        self.assertEqual(atributos.colores_del_texto('Gris azulado con negro y gris'), ['gris', 'azul', 'negro'])
        self.assertEqual(atributos.colores_del_texto('UNICO'), [])

    def test_limpiar_descarta_lo_que_no_esta_en_el_vocabulario(self):
        crudos = {
            'garment_type': 'chaqueta', 'sleeve': 'tres_cuartos', 'neckline': 'mao',
            'colors': ['negro', 'fucsia', 'negro', 'gris', 'azul', 'rojo'], 'line_hint': 'nino',
            'brand': 'Otra', 'fit': 7,
        }
        self.assertEqual(atributos.limpiar(crudos), {
            'garment_type': 'chaqueta', 'neckline': 'mao', 'colors': ['negro', 'gris', 'azul'],
        })
        self.assertEqual(atributos.limpiar('chaqueta'), {})

    def test_tipos_afines(self):
        self.assertIn('buzo', atributos.tipos_afines('chaqueta'))
        self.assertIn('conjunto', atributos.tipos_afines('leggings'))
        self.assertNotIn('leggings', atributos.tipos_afines('chaqueta'))
        self.assertNotIn('chaqueta', atributos.tipos_afines('chaqueta'))

    def test_el_vocabulario_coincide_con_las_opciones(self):
        vocabulario = atributos.vocabulario()
        for campo, opciones in atributos.CAMPOS.items():
            self.assertEqual(set(vocabulario[campo]), atributos.codigos(opciones))
        self.assertEqual(set(vocabulario['colors']), atributos.codigos(atributos.COLORES))


class ProductoTests(TestCase):
    def setUp(self):
        self.categoria = ProductCategory.objects.create(name='Pruebas atributos')
        self.marca = Brand.objects.create(name='Marca atributos')

    def _crear(self, nombre, **campos):
        return Product.objects.create(
            name=nombre, category=self.categoria, brand=self.marca, base_price=Decimal('1000'), **campos)

    def test_al_guardar_completa_lo_que_dice_el_nombre(self):
        producto = self._crear('Buzo con capucha y estampado')

        self.assertEqual(producto.garment_type, 'buzo')
        self.assertEqual(producto.neckline, 'capucha')
        self.assertEqual(producto.pattern, 'estampado')
        self.assertEqual(producto.visual_attributes_origin, atributos.ORIGEN_INFERIDO)

    def test_nunca_cambia_un_valor_ya_puesto(self):
        producto = self._crear('Chaqueta con capucha', garment_type='buzo', visual_attributes_origin='manual')

        self.assertEqual(producto.garment_type, 'buzo')
        self.assertEqual(producto.neckline, 'capucha')
        self.assertEqual(producto.visual_attributes_origin, 'manual')

    def test_colores_del_producto_de_variantes_y_nombre(self):
        producto = self._crear('Conjunto gris con negro')
        ProductVariant.objects.create(product=producto, sku='ATR-1', size='M', color='verde')
        ProductVariant.objects.create(product=producto, sku='ATR-2', size='L', color='UNICO', is_active=False)

        self.assertEqual(atributos.colores_del_producto(producto), ['verde', 'gris', 'negro'])
