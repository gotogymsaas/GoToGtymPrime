"""Atributos visuales de una prenda: tipo, manga, cuello, ajuste, diseño y color.

Son el vocabulario comun entre el catalogo y la busqueda por foto de Quantum
Coach. El modelo de vision describe la foto del cliente con estos mismos
codigos y la tienda compara contra los productos: asi la similitud se puede
explicar ("parecida en tipo y color") y nunca depende de que el modelo invente
un producto.

Los codigos viajan al Coach y se guardan en la base: no se traducen ni se
renombran. Los textos visibles van aparte, traducidos.

`inferir_*` son heuristicas conservadoras sobre el nombre y la descripcion,
igual que `linea.inferir_linea`: si el texto no lo dice, devuelven '' en vez
de adivinar. Quien administra el catalogo corrige cualquier valor en el panel.
"""
import re
import unicodedata

from django.utils.translation import gettext_lazy as _

# Version del vocabulario. Cambia si se agrega, quita o renombra un codigo, para
# que el Coach sepa con que lista se le pregunto.
VERSION_VOCABULARIO = 'v1'

TIPOS = (
    ('camiseta', _('Camiseta')),
    ('top', _('Top')),
    ('buzo', _('Buzo o saco')),
    ('chaqueta', _('Chaqueta')),
    ('blazer', _('Blazer')),
    ('leggings', _('Leggings')),
    ('pantalon', _('Pantalón')),
    ('short', _('Short')),
    ('falda', _('Falda')),
    ('vestido', _('Vestido')),
    ('conjunto', _('Conjunto')),
    ('accesorio', _('Accesorio')),
)
MANGAS = (
    ('sin_manga', _('Sin manga')),
    ('corta', _('Manga corta')),
    ('larga', _('Manga larga')),
)
CUELLOS = (
    ('redondo', _('Cuello redondo')),
    ('v', _('Cuello en V')),
    ('mao', _('Cuello mao')),
    ('alto', _('Cuello alto')),
    ('capucha', _('Con capucha')),
)
AJUSTES = (
    ('ajustado', _('Ajustado')),
    ('regular', _('Regular')),
    ('holgado', _('Holgado')),
)
DISENOS = (
    ('liso', _('Liso')),
    ('estampado', _('Estampado')),
    ('bloques', _('Bloques de color')),
)
COLORES = (
    ('negro', _('Negro')),
    ('blanco', _('Blanco')),
    ('gris', _('Gris')),
    ('azul', _('Azul')),
    ('rojo', _('Rojo')),
    ('rosa', _('Rosa')),
    ('verde', _('Verde')),
    ('amarillo', _('Amarillo')),
    ('naranja', _('Naranja')),
    ('morado', _('Morado')),
    ('beige', _('Beige')),
    ('cafe', _('Café')),
)
LINEAS = ('dama', 'caballero', 'unisex')

ORIGEN_INFERIDO = 'inferido'
ORIGEN_IA = 'ia'
ORIGEN_MANUAL = 'manual'
ORIGENES = (
    (ORIGEN_INFERIDO, 'Deducido del nombre'),
    (ORIGEN_IA, 'Propuesto por IA (revisar)'),
    (ORIGEN_MANUAL, 'Revisado en el panel'),
)

# Campo del producto -> opciones. El orden es el de la ficha del panel.
CAMPOS = {
    'garment_type': TIPOS,
    'sleeve': MANGAS,
    'neckline': CUELLOS,
    'fit': AJUSTES,
    'pattern': DISENOS,
}
MAX_COLORES = 3


def codigos(opciones):
    return frozenset(codigo for codigo, _etiqueta in opciones)


def etiqueta(opciones, codigo):
    return dict(opciones).get(codigo, '')


def vocabulario():
    """Listas cerradas que se le entregan al modelo de vision."""
    return {
        'version': VERSION_VOCABULARIO,
        'garment_type': [c for c, _e in TIPOS],
        'sleeve': [c for c, _e in MANGAS],
        'neckline': [c for c, _e in CUELLOS],
        'fit': [c for c, _e in AJUSTES],
        'pattern': [c for c, _e in DISENOS],
        'colors': [c for c, _e in COLORES],
        'line_hint': list(LINEAS),
    }


# Prendas que, sin ser del mismo tipo, cumplen un papel parecido: quien busca
# una chaqueta puede considerar un buzo, no unos leggings.
FAMILIAS = (
    frozenset({'chaqueta', 'buzo', 'blazer'}),
    frozenset({'camiseta', 'top'}),
    frozenset({'leggings', 'pantalon', 'short', 'falda'}),
)
# Un conjunto trae parte de arriba y parte de abajo.
PARTES_DE_CONJUNTO = frozenset({'camiseta', 'top', 'buzo', 'chaqueta', 'leggings', 'pantalon', 'short'})


def tipos_afines(tipo):
    afines = set()
    for familia in FAMILIAS:
        if tipo in familia:
            afines |= familia
    if tipo in PARTES_DE_CONJUNTO:
        afines.add('conjunto')
    if tipo == 'conjunto':
        afines |= PARTES_DE_CONJUNTO
    afines.discard(tipo)
    return frozenset(afines)


# --- Inferencia a partir del texto ------------------------------------------

def _normalizar(texto):
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in descompuesto if not unicodedata.combining(c)).lower()


def _palabras(texto):
    return re.findall(r'[a-z0-9]+', _normalizar(texto))


_PALABRAS_TIPO = (
    # El primero que aparezca en el texto manda: "conjunto de top y leggings"
    # es un conjunto.
    ('conjunto', ('conjunto', 'conjuntos', 'set', 'sets', 'kit')),
    ('blazer', ('blazer', 'blazers')),
    ('chaqueta', ('chaqueta', 'chaquetas', 'jacket', 'jackets', 'cortavientos', 'rompevientos', 'chamarra')),
    ('buzo', ('buzo', 'buzos', 'saco', 'sacos', 'hoodie', 'hoodies', 'sweater', 'sueter', 'sweatshirt')),
    ('top', ('top', 'tops', 'ombliguero', 'crop', 'bra', 'brasier', 'sosten')),
    ('camiseta', ('camiseta', 'camisetas', 'tshirt', 'polo', 'remera', 'playera', 'camisa', 'esqueleto')),
    ('leggings', ('leggins', 'leggings', 'legging', 'licra', 'lycra', 'malla')),
    ('short', ('short', 'shorts', 'pantaloneta', 'bermuda')),
    ('pantalon', ('pantalon', 'pantalones', 'jogger', 'joggers', 'pants')),
    ('falda', ('falda', 'faldas', 'skirt')),
    ('vestido', ('vestido', 'vestidos', 'dress')),
    ('accesorio', ('gorra', 'medias', 'calcetines', 'bolso', 'morral', 'guantes', 'botella', 'termo', 'banda')),
)

_PALABRAS_COLOR = {
    'negro': ('negro', 'negra', 'negros', 'negras', 'black'),
    'blanco': ('blanco', 'blanca', 'blancos', 'blancas', 'white', 'hueso', 'marfil'),
    'gris': ('gris', 'grises', 'grafito', 'plomo', 'gray', 'grey', 'carbon', 'jaspeado'),
    'azul': ('azul', 'azules', 'azulado', 'azulada', 'navy', 'marino', 'celeste', 'turquesa', 'blue', 'indigo'),
    'rojo': ('rojo', 'roja', 'rojos', 'vino', 'granate', 'red', 'burdeos'),
    'rosa': ('rosa', 'rosado', 'rosada', 'fucsia', 'pink', 'magenta'),
    'verde': ('verde', 'verdes', 'oliva', 'menta', 'green', 'militar'),
    'amarillo': ('amarillo', 'amarilla', 'mostaza', 'yellow'),
    'naranja': ('naranja', 'naranjas', 'coral', 'orange'),
    'morado': ('morado', 'morada', 'lila', 'violeta', 'purple', 'lavanda'),
    'beige': ('beige', 'arena', 'crema', 'nude', 'camel'),
    'cafe': ('cafe', 'marron', 'chocolate', 'brown'),
}
_COLOR_DE_PALABRA = {palabra: color for color, palabras in _PALABRAS_COLOR.items() for palabra in palabras}


def inferir_tipo(nombre, descripcion=''):
    """Tipo de prenda que dice el nombre (o, si no lo dice, la descripcion)."""
    for texto in (nombre, descripcion):
        palabras = _palabras(texto)
        for posicion in range(len(palabras)):
            for tipo, claves in _PALABRAS_TIPO:
                if palabras[posicion] in claves:
                    return tipo
    return ''


def inferir_manga(nombre, descripcion=''):
    texto = ' '.join(_palabras(f'{nombre} {descripcion}'))
    if re.search(r'\b(sin mangas?|esqueleto|sleeveless|tank)\b', texto):
        return 'sin_manga'
    if re.search(r'\bmangas? larga|long sleeve', texto):
        return 'larga'
    if re.search(r'\bmangas? corta|short sleeve', texto):
        return 'corta'
    return ''


def inferir_cuello(nombre, descripcion=''):
    texto = ' '.join(_palabras(f'{nombre} {descripcion}'))
    if re.search(r'\b(capucha|hoodie|hooded)\b', texto):
        return 'capucha'
    if re.search(r'\bcuello mao\b|\bmao\b', texto):
        return 'mao'
    if re.search(r'\bcuello (en )?v\b|\bv neck\b', texto):
        return 'v'
    if re.search(r'\b(cuello alto|cuello tortuga|turtleneck)\b', texto):
        return 'alto'
    if re.search(r'\bcuello redondo\b|\bcrew neck\b', texto):
        return 'redondo'
    return ''


def inferir_diseno(nombre, descripcion=''):
    texto = ' '.join(_palabras(nombre))
    if re.search(r'\b(estampado|estampada|print|grafico|geometrico)\b', texto):
        return 'estampado'
    if re.search(r'\b(paneles|panel|bloques)\b', texto):
        return 'bloques'
    return ''


def colores_del_texto(texto):
    """Familias de color que nombra un texto, en el orden en que aparecen."""
    vistos = []
    for palabra in _palabras(texto):
        color = _COLOR_DE_PALABRA.get(palabra)
        if color and color not in vistos:
            vistos.append(color)
    return vistos


def colores_del_producto(producto, variantes=None):
    """Familias de color de un producto: las de sus variantes activas y las que
    dice su nombre (las variantes a veces dicen solo "UNICO")."""
    if variantes is None:
        variantes = [v for v in producto.variants.all() if v.is_active]
    colores = []
    for texto in [v.color for v in variantes] + [producto.name]:
        for color in colores_del_texto(texto):
            if color not in colores:
                colores.append(color)
    return colores


def inferir_atributos(nombre, descripcion=''):
    """Lo que el texto dice con certeza; claves sin valor se omiten."""
    deducidos = {
        'garment_type': inferir_tipo(nombre, descripcion),
        'sleeve': inferir_manga(nombre, descripcion),
        'neckline': inferir_cuello(nombre, descripcion),
        'pattern': inferir_diseno(nombre, descripcion),
    }
    return {campo: valor for campo, valor in deducidos.items() if valor}


def limpiar(crudos):
    """Atributos de una fuente externa (el modelo de vision), reducidos al
    vocabulario cerrado. Un valor fuera de la lista se descarta, no se corrige."""
    if not isinstance(crudos, dict):
        return {}
    limpios = {}
    for campo, opciones in CAMPOS.items():
        valor = crudos.get(campo)
        if isinstance(valor, str) and valor in codigos(opciones):
            limpios[campo] = valor
    colores = crudos.get('colors')
    if isinstance(colores, list):
        validos = []
        for color in colores:
            if isinstance(color, str) and color in codigos(COLORES) and color not in validos:
                validos.append(color)
        if validos:
            limpios['colors'] = validos[:MAX_COLORES]
    linea = crudos.get('line_hint')
    if isinstance(linea, str) and linea in LINEAS:
        limpios['line_hint'] = linea
    return limpios


def resumen_visible(atributos):
    """Etiquetas traducidas de lo que se busco, para mostrarlas al cliente."""
    partes = []
    for campo, opciones in CAMPOS.items():
        if atributos.get(campo):
            partes.append(str(etiqueta(opciones, atributos[campo])))
    for color in atributos.get('colors', []):
        partes.append(str(etiqueta(COLORES, color)).lower())
    return [parte for parte in partes if parte]
