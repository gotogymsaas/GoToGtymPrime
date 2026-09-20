"""Extraccion de talla y color desde el texto libre del catalogo.

El catalogo heredado codifica talla y color dentro de `Product.name` y
`Product.description` ("tallas S, M y L", "talla unica", "Leggins gris
azulado..."). Estas funciones convierten ese texto en datos estructurados
para poder generar variantes.

Es una heuristica: cuando el texto no permite determinar talla o color con
certeza se devuelve el marcador generico correspondiente (`UNICA` / `UNICO`)
en vez de adivinar un valor.
"""
import re
import unicodedata

SIZE_UNKNOWN = 'UNICA'
COLOR_UNKNOWN = 'UNICO'

# Tallas reconocidas, de mas larga a mas corta para que "XXL" no se parta.
KNOWN_SIZES = ['XXL', 'XL', 'XS', 'S', 'M', 'L']

# Colores reconocidos. Los compuestos van primero: "gris azulado" debe ganar
# sobre "gris" cuando ambos coinciden en la misma posicion.
KNOWN_COLORS = [
    'gris azulado',
    'azul claro',
    'azul oscuro',
    'negro',
    'blanco',
    'gris',
    'azul',
    'verde',
    'naranja',
    'rojo',
    'amarillo',
    'morado',
    'rosado',
    'rosa',
    'beige',
]

COLOR_CODES = {
    'gris azulado': 'GRA',
    'azul claro': 'AZC',
    'azul oscuro': 'AZO',
    'negro': 'NEG',
    'blanco': 'BLA',
    'gris': 'GRI',
    'azul': 'AZU',
    'verde': 'VER',
    'naranja': 'NAR',
    'rojo': 'ROJ',
    'amarillo': 'AMA',
    'morado': 'MOR',
    'rosado': 'ROD',
    'rosa': 'ROS',
    'beige': 'BEI',
    COLOR_UNKNOWN: 'UNI',
}

SIZE_CODES = {
    'XXL': 'XXL',
    'XL': 'XL',
    'XS': 'XS',
    'S': 'S',
    'M': 'M',
    'L': 'L',
    SIZE_UNKNOWN: 'U',
}


def normalize(text):
    """Pasa a minusculas y elimina acentos, para comparar texto de forma estable."""
    if not text:
        return ''
    decomposed = unicodedata.normalize('NFKD', text)
    without_accents = ''.join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.lower()


def parse_sizes(text):
    """Devuelve la lista de tallas encontradas en el texto.

    Reconoce "talla unica", un bloque "tallas S, M y L" y una talla suelta
    ("talla S"). Si no reconoce nada devuelve [SIZE_UNKNOWN], de modo que el
    producto siempre termina con al menos una variante.
    """
    normalized = normalize(text)

    if re.search(r'talla\s+unica', normalized):
        return [SIZE_UNKNOWN]

    # Segmento que sigue a "talla"/"tallas" hasta el final de la frase.
    match = re.search(r'tallas?\s+([^.;]*)', normalized)
    if not match:
        return [SIZE_UNKNOWN]

    segment = match.group(1)
    found = []
    for token in re.findall(r'\b(xxl|xl|xs|s|m|l)\b', segment):
        size = token.upper()
        if size not in found:
            found.append(size)

    if not found:
        return [SIZE_UNKNOWN]

    # Se devuelven en el orden convencional, no en el orden del texto.
    return [size for size in KNOWN_SIZES if size in found]


def parse_color(text):
    """Devuelve el primer color reconocido en el texto, o COLOR_UNKNOWN.

    Ante empate de posicion gana el nombre mas largo, para que "gris azulado"
    no se reduzca a "gris".
    """
    normalized = normalize(text)

    best = None
    for color in KNOWN_COLORS:
        position = normalized.find(color)
        if position == -1:
            continue
        candidate = (position, -len(color), color)
        if best is None or candidate < best:
            best = candidate

    return best[2] if best else COLOR_UNKNOWN


def build_sku(product_id, size, color):
    """SKU determinista y legible: GTG-0001-S-GRA."""
    size_code = SIZE_CODES.get(size, re.sub(r'[^A-Z0-9]', '', size.upper())[:3] or 'U')
    color_code = COLOR_CODES.get(color, normalize(color).upper()[:3] or 'UNI')
    return f"GTG-{int(product_id):04d}-{size_code}-{color_code}"


def parse_product_variants(product_id, name, description):
    """Devuelve la lista de variantes a crear para un producto.

    Cada elemento es un dict con `sku`, `size` y `color`. El color se busca
    en el nombre (que es donde el catalogo lo indica) y la talla en el
    nombre y la descripcion combinados.
    """
    color = parse_color(name)
    sizes = parse_sizes(f"{name} {description}")

    return [
        {
            'sku': build_sku(product_id, size, color),
            'size': size,
            'color': color,
        }
        for size in sizes
    ]
