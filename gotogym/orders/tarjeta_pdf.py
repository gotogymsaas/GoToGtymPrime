"""PDF de la tarjeta de regalo, para adjuntarlo al correo de quien la recibe.

Se dibuja en vectores con reportlab: nitido a cualquier zoom o impresion, y
con texto real, asi que el codigo se puede seleccionar y copiar. Tamaño A5
horizontal.

Misma estetica que el correo: fondo tinta, cinta turquesa vertical y dorada
horizontal, el valor en grande, el codigo en un recuadro y la vigencia. La
tipografia es TT Norms Pro (`orders/fuentes/`, generada con
`scripts/generar_fuentes_pdf.py`); el PDF incrusta solo las letras que usa. Si
las fuentes faltan, sale con Helvetica. Los textos llegan en el idioma
activo; quien llama fija el de la compra.
"""
import io
import logging
from pathlib import Path

from django.contrib.staticfiles import finders
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A5, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

FUENTES = Path(__file__).resolve().parent / 'fuentes'
LOGO = 'images/logo-gotogym-symbol-transparent.png'

# Se dibuja sobre una cuadricula de 1654 x 1165 unidades (A5 a 200 ppp) y se
# escala a puntos: asi las medidas son las mismas del diseño aprobado.
ANCHO, ALTO = 1654, 1165
ESCALA = landscape(A5)[0] / ANCHO


def _color(r, g, b):
    return Color(r / 255, g / 255, b / 255)


TINTA = _color(16, 16, 18)
PANEL = _color(29, 29, 34)
TURQUESA = _color(15, 191, 176)
DORADO = _color(212, 180, 106)
DORADO_OSCURO = _color(168, 137, 63)
BLANCO = _color(255, 255, 255)
GRIS = _color(160, 160, 168)
GRIS_CLARO = _color(201, 201, 207)

CINTA_X, CINTA_ANCHO = 1330, 64
CINTA_Y, CINTA_ALTO = 250, 22
MARGEN = 110
ANCHO_UTIL = CINTA_X - MARGEN - 70

_fuentes: dict[str, str] = {}


def _fuente(tipo):
    """Nombre registrado de la cara 'fuerte' o 'normal' (TT Norms, o
    Helvetica si los archivos no estan)."""
    if not _fuentes:
        try:
            pdfmetrics.registerFont(TTFont('GTG-Fuerte', str(FUENTES / 'tt-norms-extrabold.ttf')))
            pdfmetrics.registerFont(TTFont('GTG-Normal', str(FUENTES / 'tt-norms-regular.ttf')))
            _fuentes.update(fuerte='GTG-Fuerte', normal='GTG-Normal')
        except Exception:
            logger.warning('No se pudieron cargar las fuentes del PDF de la tarjeta; se usa Helvetica', exc_info=True)
            _fuentes.update(fuerte='Helvetica-Bold', normal='Helvetica')
    return _fuentes[tipo]


def _pesos(valor):
    return '$' + f'{int(round(float(valor))):,}'.replace(',', '.')


class _Lienzo:
    """Dibuja con coordenadas desde arriba a la izquierda (como el diseño)."""

    def __init__(self, c):
        self.c = c

    def rect(self, x, y, ancho, alto, color):
        self.c.setFillColor(color)
        self.c.rect(x, ALTO - y - alto, ancho, alto, stroke=0, fill=1)

    def ancho(self, texto, tipo, tamano, espacio=0):
        return pdfmetrics.stringWidth(texto, _fuente(tipo), tamano) + espacio * max(len(texto) - 1, 0)

    def texto(self, x, y, texto, tipo, tamano, color, espacio=0):
        """`y` es la parte de arriba del texto. Un solo objeto de texto (con
        separacion entre letras si hace falta) para que se copie entero."""
        objeto = self.c.beginText()
        objeto.setTextOrigin(x, ALTO - y - tamano * 0.8)
        objeto.setFont(_fuente(tipo), tamano)
        objeto.setFillColor(color)
        objeto.setCharSpace(espacio)
        objeto.textOut(texto)
        self.c.drawText(objeto)

    def lineas(self, texto, tipo, tamano, ancho_maximo, maximo):
        """Parte el texto en lineas que caben (como mucho `maximo`)."""
        lineas = []
        for parrafo in texto.splitlines() or ['']:
            actual = ''
            for palabra in parrafo.split():
                prueba = f'{actual} {palabra}'.strip()
                if self.ancho(prueba, tipo, tamano) <= ancho_maximo:
                    actual = prueba
                else:
                    if actual:
                        lineas.append(actual)
                    actual = palabra
            lineas.append(actual)
        if len(lineas) > maximo:
            lineas = lineas[:maximo]
            ultima = lineas[-1]
            while ultima and self.ancho(ultima + ' …', tipo, tamano) > ancho_maximo:
                ultima = ultima.rsplit(' ', 1)[0] if ' ' in ultima else ultima[:-1]
            lineas[-1] = ultima + ' …'
        return lineas


def _dibujar(c, tarjeta):
    c.scale(ESCALA, ESCALA)
    lienzo = _Lienzo(c)
    lienzo.rect(0, 0, ANCHO, ALTO, TINTA)

    # Cinta: vertical turquesa, horizontal dorada y el cruce mas oscuro.
    lienzo.rect(CINTA_X, 0, CINTA_ANCHO, ALTO, TURQUESA)
    lienzo.rect(0, CINTA_Y, ANCHO, CINTA_ALTO, DORADO)
    lienzo.rect(CINTA_X, CINTA_Y, CINTA_ANCHO, CINTA_ALTO, DORADO_OSCURO)

    # Cabecera: logo, marca y rotulo.
    x: float = MARGEN
    ruta_logo = finders.find(LOGO)
    if ruta_logo:
        alto_logo = 96
        ancho_logo = alto_logo * 1141 / 739  # proporcion del archivo del logo
        c.drawImage(ruta_logo, MARGEN, ALTO - 78 - alto_logo, ancho_logo, alto_logo, mask='auto')
        x = MARGEN + ancho_logo
    lienzo.texto(x + 26, 86, 'GoToGym', 'fuerte', 58, BLANCO)
    lienzo.texto(x + 28, 162, gettext('Tarjeta de regalo').upper(), 'fuerte', 30, TURQUESA, espacio=6)

    # Valor.
    y = CINTA_Y + CINTA_ALTO + 46
    valor = _pesos(tarjeta.initial_amount)
    lienzo.texto(MARGEN - 6, y, valor, 'fuerte', 150, BLANCO)
    lienzo.texto(MARGEN + lienzo.ancho(valor, 'fuerte', 150) + 18, y + 92, 'COP', 'fuerte', 30, GRIS, espacio=4)
    y += 170

    # Para / De parte de.
    for etiqueta, nombre in ((gettext('Para'), tarjeta.recipient_name), (gettext('De parte de'), tarjeta.sender_name)):
        lienzo.texto(MARGEN, y, etiqueta, 'normal', 38, GRIS_CLARO)
        lienzo.texto(MARGEN + lienzo.ancho(etiqueta + '  ', 'normal', 38), y, nombre, 'fuerte', 38, DORADO)
        y += 52

    # Dedicatoria, con la barra dorada como en el correo (como mucho tres
    # lineas: siempre termina antes de la franja del codigo).
    if tarjeta.message:
        y += 20
        lineas = lienzo.lineas(tarjeta.message, 'normal', 34, ANCHO_UTIL - 60, 3)
        alto = 34 + len(lineas) * 46
        lienzo.rect(MARGEN, y, ANCHO_UTIL, alto, PANEL)
        lienzo.rect(MARGEN, y, 8, alto, DORADO)
        for indice, linea in enumerate(lineas):
            lienzo.texto(MARGEN + 36, y + 20 + indice * 46, linea, 'normal', 34, BLANCO)

    # Codigo y vigencia en una franja fija de abajo.
    y_codigo = ALTO - 356
    lienzo.texto(MARGEN, y_codigo, gettext('Tu código').upper(), 'fuerte', 30, GRIS, espacio=5)
    caja_y = y_codigo + 44
    ancho_codigo = lienzo.ancho(tarjeta.display_code, 'fuerte', 62, espacio=8)
    c.setFillColor(PANEL)
    c.setStrokeColor(DORADO)
    c.setLineWidth(3)
    c.roundRect(MARGEN, ALTO - caja_y - 100, ancho_codigo + 60, 100, 16, stroke=1, fill=1)
    lienzo.texto(MARGEN + 30, caja_y + 22, tarjeta.display_code, 'fuerte', 62, BLANCO, espacio=8)
    vence = date_format(timezone.localtime(tarjeta.expires_at), 'DATE_FORMAT') if tarjeta.expires_at else ''
    lienzo.texto(MARGEN, caja_y + 124, gettext('Válida hasta el %(fecha)s') % {'fecha': vence}, 'normal', 38, DORADO)

    # Instrucciones al pie.
    instrucciones = gettext(
        'Úsala en gotogym.store: inicia sesión y escribe el código en "Cupón o tarjeta de regalo" al pagar. '
        'Sirve para una o varias compras hasta su vencimiento. No se cambia por dinero.'
    )
    for indice, linea in enumerate(lienzo.lineas(instrucciones, 'normal', 25, ANCHO_UTIL, 2)):
        lienzo.texto(MARGEN, ALTO - 104 + indice * 36, linea, 'normal', 25, GRIS)


def pdf_de_tarjeta(tarjeta):
    """Bytes del PDF de la tarjeta."""
    salida = io.BytesIO()
    c = canvas.Canvas(salida, pagesize=landscape(A5), pageCompression=1)
    c.setTitle(gettext('Tarjeta de regalo GoToGym'))
    c.setAuthor('GoToGym')
    _dibujar(c, tarjeta)
    c.showPage()
    c.save()
    return salida.getvalue()
