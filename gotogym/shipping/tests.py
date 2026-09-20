"""Cotizacion de envio: tarifa determinista por ciudad, no un numero fijo."""
from decimal import Decimal

from django.test import SimpleTestCase

from .services import (
    FLAT_RATE_MAIN_CITY,
    FLAT_RATE_OTHER_CITY,
    FREE_SHIPPING_THRESHOLD,
    get_mock_quote,
    get_mock_quote_estimate,
    normalize_city,
)


class NormalizeCityTests(SimpleTestCase):
    def test_ignora_acentos_y_mayusculas(self):
        self.assertEqual(normalize_city('Bogotá'), 'bogota')
        self.assertEqual(normalize_city('MEDELLÍN'), 'medellin')

    def test_ignora_espacios_al_borde(self):
        self.assertEqual(normalize_city('  Cali  '), 'cali')

    def test_ciudad_vacia_no_rompe(self):
        self.assertEqual(normalize_city(''), '')
        self.assertEqual(normalize_city(None), '')


class GetMockQuoteTests(SimpleTestCase):
    def test_ciudad_principal_tiene_tarifa_mas_baja(self):
        cotizacion = get_mock_quote('Bogotá', Decimal('50000'))
        self.assertEqual(cotizacion['cost'], FLAT_RATE_MAIN_CITY)
        self.assertEqual(cotizacion['estimated_days'], 3)

    def test_ciudad_no_principal_tiene_tarifa_mas_alta(self):
        cotizacion = get_mock_quote('Leticia', Decimal('50000'))
        self.assertEqual(cotizacion['cost'], FLAT_RATE_OTHER_CITY)
        self.assertGreater(cotizacion['estimated_days'], 3)

    def test_tarifa_principal_es_mas_barata_que_la_de_resto_del_pais(self):
        self.assertLess(FLAT_RATE_MAIN_CITY, FLAT_RATE_OTHER_CITY)

    def test_envio_gratis_por_encima_del_umbral(self):
        cotizacion = get_mock_quote('Leticia', FREE_SHIPPING_THRESHOLD)
        self.assertEqual(cotizacion['cost'], Decimal('0.00'))

    def test_envio_no_es_gratis_justo_debajo_del_umbral(self):
        cotizacion = get_mock_quote('Leticia', FREE_SHIPPING_THRESHOLD - Decimal('1'))
        self.assertGreater(cotizacion['cost'], Decimal('0.00'))

    def test_reconoce_la_ciudad_sin_importar_acentos_ni_mayusculas(self):
        self.assertEqual(
            get_mock_quote('bogotá', Decimal('1'))['cost'],
            get_mock_quote('BOGOTA', Decimal('1'))['cost'],
        )


class GetMockQuoteEstimateTests(SimpleTestCase):
    def test_estimacion_es_la_tarifa_mas_barata_posible(self):
        self.assertEqual(get_mock_quote_estimate(Decimal('50000')), FLAT_RATE_MAIN_CITY)

    def test_estimacion_gratis_por_encima_del_umbral(self):
        self.assertEqual(get_mock_quote_estimate(FREE_SHIPPING_THRESHOLD), Decimal('0.00'))
