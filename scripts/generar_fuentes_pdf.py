"""Genera las fuentes TrueType que usa el PDF de la tarjeta de regalo.

TT Norms Pro viene en OpenType con contornos CFF, y reportlab (que dibuja el
PDF) solo incrusta TrueType. Este script recorta cada cara al alfabeto latino
(el mismo rango que los subconjuntos web) y convierte sus curvas a TrueType.
El resultado va a `gotogym/orders/fuentes/`, fuera de `static`: el sitio no lo
publica y el PDF incrusta solo las letras que usa.

Se corre a mano, una vez, cuando cambie la tipografia:

    python scripts/generar_fuentes_pdf.py

Necesita fontTools (no es dependencia de la aplicacion, solo de este script).
"""
from pathlib import Path

from fontTools import subset
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / 'design' / 'tipografia-fuente'
DESTINO = RAIZ / 'gotogym' / 'orders' / 'fuentes'

CARAS = {
    'tt-norms-extrabold.ttf': ORIGEN / 'Titulo' / 'TT Norms Pro ExtraBold.otf',
    'tt-norms-regular.ttf': ORIGEN / 'Cuerpo de Mensaje' / 'TT Norms Pro Regular.otf',
}

# Mismo rango que los subconjuntos web (ver design/tipografia-fuente/LEEME.md).
UNICODES = (
    'U+0000-00FF,U+0100-017F,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,'
    'U+2000-206F,U+2074,U+20AC,U+2122,U+2190-21FF,U+2212,U+2215,U+FEFF,U+FFFD'
)

ERROR_MAXIMO = 1.0  # unidades de diseño al pasar de curvas cubicas a cuadraticas


def _recortar(fuente):
    opciones = subset.Options()
    opciones.layout_features = []  # reportlab no aplica sustituciones ni kerning
    opciones.name_IDs = ['*']
    opciones.notdef_outline = True
    subconjunto = subset.Subsetter(opciones)
    subconjunto.populate(unicodes=subset.parse_unicodes(UNICODES))
    subconjunto.subset(fuente)


def _a_truetype(fuente):
    """Convierte contornos CFF a glyf (receta de fontTools, otf2ttf)."""
    orden = fuente.getGlyphOrder()
    glifos = fuente.getGlyphSet()
    cuadraticos = {}
    for nombre in orden:
        pluma = TTGlyphPen(glifos)
        glifos[nombre].draw(Cu2QuPen(pluma, ERROR_MAXIMO, reverse_direction=True))
        cuadraticos[nombre] = pluma.glyph()

    fuente['loca'] = newTable('loca')
    fuente['glyf'] = glyf = newTable('glyf')
    glyf.glyphOrder = orden
    glyf.glyphs = cuadraticos
    del fuente['CFF ']
    if 'VORG' in fuente:
        del fuente['VORG']
    glyf.compile(fuente)

    hmtx = fuente['hmtx']
    for nombre, glifo in glyf.glyphs.items():
        if hasattr(glifo, 'xMin'):
            hmtx[nombre] = (hmtx[nombre][0], glifo.xMin)

    fuente['maxp'] = maxp = newTable('maxp')
    maxp.tableVersion = 0x00010000
    maxp.maxZones = 1
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.maxComponentElements = max(
        (len(getattr(g, 'components', []) or []) for g in glyf.glyphs.values()), default=0,
    )
    maxp.compile(fuente)

    post = fuente['post']
    post.formatType = 2.0
    post.extraNames = []
    post.mapping = {}
    post.glyphOrder = orden
    try:
        post.compile(fuente)
    except OverflowError:
        post.formatType = 3.0
    fuente.sfntVersion = '\000\001\000\000'


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nombre, origen in CARAS.items():
        fuente = TTFont(origen)
        _recortar(fuente)
        _a_truetype(fuente)
        salida = DESTINO / nombre
        fuente.save(salida)
        print(f'{salida.relative_to(RAIZ)}: {salida.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
