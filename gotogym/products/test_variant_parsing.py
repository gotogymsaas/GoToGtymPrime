"""Parseo de talla y color desde el texto libre del catalogo."""
from django.test import SimpleTestCase

from .variant_parsing import (
    COLOR_UNKNOWN,
    SIZE_UNKNOWN,
    build_sku,
    parse_color,
    parse_product_variants,
    parse_sizes,
)

# Los siete productos reales del catalogo, con el resultado esperado.
CATALOG_CASES = [
    (
        1,
        'Leggins gris azulado para dama',
        'Leggins color gris, tallas S, M y L. Hecho en Microfibra. Uso deportivo y casual.',
        ['S', 'M', 'L'],
        'gris azulado',
    ),
    (
        2,
        'Pantalon verde',
        'Pantalon verde para caballero, talla unica, en licra.',
        [SIZE_UNKNOWN],
        'verde',
    ),
    (
        3,
        'Chaqueta naranja + grafeno cremallera caballero',
        'Chaqueta naranja con grafeno, para caballero, talla unica. Cierre de cremallera. Hecha en licra.',
        [SIZE_UNKNOWN],
        'naranja',
    ),
    (
        4,
        'Conjunto para dama en gris con negro',
        'Chaqueta de color gris con negro, con cierre de cremallera, mas leggins gris con franja negra. '
        'Hecho en Microfibra. Para dama. Tallas S, M y L.',
        ['S', 'M', 'L'],
        'gris',
    ),
    (
        5,
        'Conjunto gris azulado deportivo para dama',
        'Conjunto de chaqueta ombliguera manga larga con leggins, color gris azulado con franja negra. '
        'Para dama, hecho en Mirofibra. Tallas S, M y L',
        ['S', 'M', 'L'],
        'gris azulado',
    ),
    (
        6,
        'Saco negro gris',
        'Saco negro con gris para dama, talla S, elaborado en Microfibra.',
        ['S'],
        'negro',
    ),
    (
        7,
        'X5 Generation Mujer',
        'Producto GoToGym de alta costura personalizada exclusiva.',
        [SIZE_UNKNOWN],
        COLOR_UNKNOWN,
    ),
]


class RealCatalogParsingTests(SimpleTestCase):
    def test_every_real_product_parses_as_expected(self):
        for product_id, name, description, expected_sizes, expected_color in CATALOG_CASES:
            with self.subTest(product=name):
                variants = parse_product_variants(product_id, name, description)
                self.assertEqual([v['size'] for v in variants], expected_sizes)
                self.assertEqual({v['color'] for v in variants}, {expected_color})

    def test_every_real_product_yields_at_least_one_variant(self):
        for product_id, name, description, _sizes, _color in CATALOG_CASES:
            with self.subTest(product=name):
                self.assertGreaterEqual(len(parse_product_variants(product_id, name, description)), 1)

    def test_skus_are_unique_across_the_real_catalog(self):
        skus = [
            variant['sku']
            for product_id, name, description, _s, _c in CATALOG_CASES
            for variant in parse_product_variants(product_id, name, description)
        ]
        self.assertEqual(len(skus), len(set(skus)))


class SizeParsingTests(SimpleTestCase):
    def test_talla_unica_with_and_without_accent(self):
        self.assertEqual(parse_sizes('talla unica'), [SIZE_UNKNOWN])
        self.assertEqual(parse_sizes('talla única'), [SIZE_UNKNOWN])

    def test_sizes_are_returned_in_conventional_order(self):
        self.assertEqual(parse_sizes('tallas L, S y M'), ['S', 'M', 'L'])

    def test_comma_separated_sizes_without_conjunction(self):
        self.assertEqual(parse_sizes('tallas S, M, L'), ['S', 'M', 'L'])

    def test_extended_sizes(self):
        self.assertEqual(parse_sizes('tallas XS, S, XL y XXL'), ['XXL', 'XL', 'XS', 'S'])

    def test_unparseable_text_falls_back_to_generic_size(self):
        self.assertEqual(parse_sizes('Producto sin informacion de medidas'), [SIZE_UNKNOWN])

    def test_size_words_in_other_sentences_are_not_picked_up(self):
        # "Microfibra" no debe interpretarse como talla M.
        self.assertEqual(parse_sizes('Hecho en Microfibra. Uso casual.'), [SIZE_UNKNOWN])


class ColorParsingTests(SimpleTestCase):
    def test_compound_color_wins_over_its_prefix(self):
        self.assertEqual(parse_color('Leggins gris azulado para dama'), 'gris azulado')

    def test_first_color_in_the_name_wins(self):
        self.assertEqual(parse_color('Saco negro gris'), 'negro')

    def test_unknown_color_is_not_invented(self):
        self.assertEqual(parse_color('X5 Generation Mujer'), COLOR_UNKNOWN)

    def test_accents_do_not_break_detection(self):
        self.assertEqual(parse_color('Chaqueta VERDE limón'), 'verde')


class SkuTests(SimpleTestCase):
    def test_sku_format_is_stable_and_padded(self):
        self.assertEqual(build_sku(1, 'S', 'negro'), 'GTG-0001-S-NEG')
        self.assertEqual(build_sku(42, SIZE_UNKNOWN, COLOR_UNKNOWN), 'GTG-0042-U-UNI')

    def test_compound_color_has_its_own_code(self):
        self.assertNotEqual(build_sku(1, 'S', 'gris'), build_sku(1, 'S', 'gris azulado'))
