"""Linea de la prenda (dama / caballero / unisex) deducida del catalogo."""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from .linea import CABALLERO, DAMA, UNISEX, inferir_linea, lineas_compatibles
from .models import Product, ProductCategory


class InferirLineaTests(SimpleTestCase):
    def test_lee_la_linea_de_los_nombres_reales_del_catalogo(self):
        casos = {
            'Leggins gris azulado para dama': DAMA,
            'Chaqueta naranja + grafeno cremallera caballero': CABALLERO,
            'X5 Generation Mujer': DAMA,
            'Camiseta blanca con estampado geometrico para caballero': CABALLERO,
            'Top Unisex de entrenamiento': UNISEX,
        }
        for nombre, esperada in casos.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(inferir_linea(nombre), esperada)

    def test_sin_la_palabra_en_el_nombre_mira_la_descripcion(self):
        self.assertEqual(inferir_linea('Pantalon verde', 'Pantalon verde para caballero, talla unica.'), CABALLERO)
        self.assertEqual(inferir_linea('Saco negro gris', 'Saco negro con gris para dama, talla S.'), DAMA)

    def test_manda_el_nombre_sobre_la_descripcion(self):
        self.assertEqual(inferir_linea('Chaqueta para caballero', 'Combina con el top de dama.'), CABALLERO)

    def test_no_adivina_si_no_lo_dice_o_dice_las_dos(self):
        self.assertEqual(inferir_linea('Camiseta DryFit', 'Tela fresca.'), '')
        self.assertEqual(inferir_linea('Conjunto dama y caballero'), '')

    def test_no_confunde_palabras_que_solo_contienen_las_letras(self):
        # "Manga", "Damasco" o "Hombrera" no dicen la linea.
        self.assertEqual(inferir_linea('Chaqueta manga larga con hombreras', 'Estampado damasco.'), '')

    def test_tildes_y_mayusculas_no_importan(self):
        self.assertEqual(inferir_linea('CAMISETA PARA HOMBRE'), CABALLERO)
        self.assertEqual(inferir_linea('Blusa Femenína'), DAMA)

    def test_unisex_sirve_a_ambas_preferencias(self):
        self.assertEqual(lineas_compatibles(DAMA), (DAMA, UNISEX))
        self.assertEqual(lineas_compatibles(CABALLERO), (CABALLERO, UNISEX))
        self.assertEqual(lineas_compatibles(''), ())


class LineaAlGuardarTests(TestCase):
    def setUp(self):
        self.categoria = ProductCategory.objects.create(name='Pruebas de linea')

    def _crear(self, **campos):
        return Product.objects.create(category=self.categoria, base_price=Decimal('1.0000'), **campos)

    def test_un_producto_nuevo_sin_linea_la_toma_de_su_texto(self):
        self.assertEqual(self._crear(name='Leggins negro para dama').line, DAMA)

    def test_la_linea_elegida_a_mano_no_se_sobrescribe(self):
        producto = self._crear(name='Chaqueta para caballero', line=UNISEX)
        producto.save()
        producto.refresh_from_db()
        self.assertEqual(producto.line, UNISEX)

    def test_sin_pistas_queda_sin_clasificar(self):
        self.assertEqual(self._crear(name='Camiseta DryFit').line, '')

    def test_la_migracion_clasifico_el_catalogo_semilla(self):
        # 0004 siembra "Leggins gris azulado para dama" y "Pantalon verde"
        # (caballero solo en la descripcion); 0017 los clasifica.
        self.assertEqual(Product.objects.get(name='Leggins gris azulado para dama').line, DAMA)
        pantalon = Product.objects.filter(name__startswith='Pantalon verde').first()
        if pantalon is not None:
            self.assertEqual(pantalon.line, CABALLERO)
