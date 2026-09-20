"""Cotizacion de envio MOCK: tarifa determinista por ciudad, no un numero
fijo desconectado del pedido.

No consulta ninguna transportadora real. Es una tarifa plana segun si la
ciudad es una de las principales o "resto del pais", con envio gratis por
encima de un umbral de subtotal.
"""
import unicodedata
from decimal import Decimal

MAIN_CITIES = {'bogota', 'medellin', 'cali', 'barranquilla', 'bucaramanga'}

FLAT_RATE_MAIN_CITY = Decimal('12000.00')
FLAT_RATE_OTHER_CITY = Decimal('22000.00')
FREE_SHIPPING_THRESHOLD = Decimal('300000.00')

CARRIER_NAME = 'GoToGym Envios (mock)'


def normalize_city(city):
    decomposed = unicodedata.normalize('NFKD', city or '')
    sin_acentos = ''.join(c for c in decomposed if not unicodedata.combining(c))
    return sin_acentos.strip().lower()


def get_mock_quote(city, subtotal):
    """Cotizacion completa para una ciudad y un subtotal dados.

    Devuelve un dict con `carrier_name`, `method_name`, `cost` y
    `estimated_days`. El envio es gratis si el subtotal alcanza el umbral,
    sin importar la ciudad.
    """
    es_ciudad_principal = normalize_city(city) in MAIN_CITIES
    costo = FLAT_RATE_MAIN_CITY if es_ciudad_principal else FLAT_RATE_OTHER_CITY
    dias_estimados = 3 if es_ciudad_principal else 6

    if subtotal >= FREE_SHIPPING_THRESHOLD:
        costo = Decimal('0.00')

    return {
        'carrier_name': CARRIER_NAME,
        'method_name': 'Estandar' if es_ciudad_principal else 'Estandar (nacional)',
        'cost': costo,
        'estimated_days': dias_estimados,
    }


def get_mock_quote_estimate(subtotal):
    """Estimacion sin direccion todavia: la tarifa mas baja posible, para
    mostrar "desde $X" en el carrito antes de pedir ciudad de entrega."""
    if subtotal >= FREE_SHIPPING_THRESHOLD:
        return Decimal('0.00')
    return FLAT_RATE_MAIN_CITY
