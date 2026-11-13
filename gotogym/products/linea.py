"""Linea de una prenda: dama, caballero o unisex.

El catalogo la escribe dentro del nombre o la descripcion ("Leggins gris para
dama", "Pantalon verde para caballero"). `inferir_linea` la convierte en un
dato estructurado para filtrar la tienda y para que Quantum Coach recomiende
prendas de la linea que la persona busca.

Es una heuristica conservadora: si el texto no la dice, o dice las dos sin
"unisex", devuelve '' (sin clasificar) en vez de adivinar. Quien administra el
catalogo la corrige en el panel.
"""
import re
import unicodedata

DAMA = 'dama'
CABALLERO = 'caballero'
UNISEX = 'unisex'

OPCIONES = (
    (DAMA, 'Dama'),
    (CABALLERO, 'Caballero'),
    (UNISEX, 'Unisex'),
)

# Palabras que delatan cada linea, ya sin tildes y en minusculas.
_PALABRAS = {
    DAMA: ('dama', 'damas', 'mujer', 'mujeres', 'femenino', 'femenina', 'women', 'woman', 'womens'),
    CABALLERO: ('caballero', 'caballeros', 'hombre', 'hombres', 'masculino', 'masculina', 'men', 'man', 'mens'),
    UNISEX: ('unisex',),
}

# Sinonimos que se suman al texto de busqueda: quien escribe "hombre" debe
# encontrar las prendas de caballero aunque su nombre diga "caballero".
SINONIMOS = {
    DAMA: 'dama mujer mujeres femenino women',
    CABALLERO: 'caballero hombre hombres masculino men',
    UNISEX: 'unisex dama mujer caballero hombre',
}


def _palabras(texto):
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    sin_tildes = ''.join(c for c in descompuesto if not unicodedata.combining(c)).lower()
    return set(re.findall(r'[a-z]+', sin_tildes))


def _linea_de(texto):
    palabras = _palabras(texto)
    if palabras & set(_PALABRAS[UNISEX]):
        return UNISEX
    dama = bool(palabras & set(_PALABRAS[DAMA]))
    caballero = bool(palabras & set(_PALABRAS[CABALLERO]))
    if dama and caballero:
        return None  # dice las dos: no se adivina
    if dama:
        return DAMA
    if caballero:
        return CABALLERO
    return ''


def inferir_linea(nombre, descripcion=''):
    """Linea que dice el texto del producto, o '' si no la dice con certeza.

    Manda el nombre; la descripcion solo se mira si el nombre no dice nada."""
    del_nombre = _linea_de(nombre)
    if del_nombre is None:
        return ''
    if del_nombre:
        return del_nombre
    return _linea_de(descripcion) or ''


def lineas_compatibles(preferencia):
    """Lineas que sirven a quien prefiere `preferencia` (incluye unisex)."""
    if preferencia in (DAMA, CABALLERO):
        return (preferencia, UNISEX)
    return ()
