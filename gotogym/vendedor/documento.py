"""Lectura de un archivo que el cliente adjunta a Quantum Coach.

El archivo nunca se guarda: se lee en memoria, se extrae su texto, se ocultan
los datos personales evidentes (correos, enlaces y cifras largas como
telefonos, cedulas o tarjetas) y solo un extracto acotado viaja al Coach en el
turno (`attachment`). El nombre del archivo no viaja.

Formatos: PDF con texto (uno escaneado no tiene texto que leer), Excel
(.xlsx), CSV y texto plano. El formato se reconoce por el contenido, no por la
extension que declara el navegador.
"""
import csv
import io
import logging
import re
import unicodedata
import zipfile
from dataclasses import dataclass

from .contrato import FORMATOS_ADJUNTO, MAX_LARGO_EXTRACTO

logger = logging.getLogger(__name__)

FORMATOS = FORMATOS_ADJUNTO

MAX_BYTES_SUBIDA = 5 * 1024 * 1024
# Topes de lectura: un archivo pequeno puede esconder miles de paginas o filas.
MAX_PAGINAS_PDF = 15
MAX_HOJAS = 5
MAX_FILAS = 400
MAX_COLUMNAS = 30
# Un .xlsx es un zip: se mide lo que ocuparia descomprimido antes de abrirlo.
MAX_BYTES_DESCOMPRIMIDOS = 25 * 1024 * 1024
# Se deja de leer al juntar esto; el extracto final es mas corto.
MAX_LARGO_LECTURA = 20_000
# Lo que viaja al Coach (MAX_LARGO_EXTRACTO) cabe en el presupuesto del turno
# junto al catalogo.

OCULTO = '[oculto]'


class DocumentoInvalido(Exception):
    """`codigo`: `vacio`, `grande`, `formato`, `ilegible`, `protegido`, `sin_texto`."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


@dataclass(frozen=True)
class DocumentoLeido:
    formato: str
    extracto: str
    recortado: bool


# --- Formato ---------------------------------------------------------------

def _es_xlsx(datos):
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as archivo:
            nombres = set(archivo.namelist())
            if 'xl/workbook.xml' not in nombres:
                return False
            if sum(info.file_size for info in archivo.infolist()) > MAX_BYTES_DESCOMPRIMIDOS:
                raise DocumentoInvalido('grande')
            return True
    except zipfile.BadZipFile:
        return False


def _decodificar(datos):
    """Texto de un archivo plano, o `DocumentoInvalido('formato')` si es binario."""
    if b'\x00' in datos[:4096]:
        raise DocumentoInvalido('formato')
    for codificacion in ('utf-8-sig', 'cp1252'):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise DocumentoInvalido('formato')


def detectar_formato(datos, nombre=''):
    if datos.startswith(b'%PDF-'):
        return 'pdf'
    if datos.startswith(b'PK\x03\x04'):
        if _es_xlsx(datos):
            return 'xlsx'
        raise DocumentoInvalido('formato')
    texto = _decodificar(datos)
    # Un plano con muchos caracteres de control no es texto.
    controles = sum(1 for c in texto[:4096] if unicodedata.category(c) == 'Cc' and c not in '\n\r\t')
    if controles > 8:
        raise DocumentoInvalido('formato')
    return 'csv' if (nombre or '').lower().endswith('.csv') else 'txt'


# --- Lectura por formato -------------------------------------------------------

def _leer_pdf(datos):
    from pypdf import PdfReader

    try:
        lector = PdfReader(io.BytesIO(datos))
        if lector.is_encrypted and not lector.decrypt(''):
            raise DocumentoInvalido('protegido')
        partes, largo = [], 0
        for pagina in lector.pages[:MAX_PAGINAS_PDF]:
            texto = pagina.extract_text() or ''
            partes.append(texto)
            largo += len(texto)
            if largo >= MAX_LARGO_LECTURA:
                break
    except DocumentoInvalido:
        raise
    except Exception as error:  # pypdf lanza errores muy variados con PDF rotos
        logger.info('Vendedor: PDF ilegible (%s).', type(error).__name__)
        raise DocumentoInvalido('ilegible') from None
    return '\n\n'.join(partes)


def _celda(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _filas_a_texto(filas):
    lineas, largo = [], 0
    for fila in filas:
        celdas = [c for c in (_celda(v) for v in list(fila)[:MAX_COLUMNAS]) if c]
        if not celdas:
            continue
        linea = ' | '.join(celdas)
        lineas.append(linea)
        largo += len(linea)
        if len(lineas) >= MAX_FILAS or largo >= MAX_LARGO_LECTURA:
            break
    return '\n'.join(lineas)


def _leer_xlsx(datos):
    from openpyxl import load_workbook

    try:
        libro = load_workbook(io.BytesIO(datos), read_only=True, data_only=True)
    except Exception as error:
        logger.info('Vendedor: Excel ilegible (%s).', type(error).__name__)
        raise DocumentoInvalido('ilegible') from None
    try:
        partes = []
        for hoja in libro.worksheets[:MAX_HOJAS]:
            texto = _filas_a_texto(hoja.iter_rows(max_row=MAX_FILAS, max_col=MAX_COLUMNAS, values_only=True))
            if texto:
                partes.append(f'[{hoja.title}]\n{texto}')
    except Exception as error:
        logger.info('Vendedor: Excel ilegible (%s).', type(error).__name__)
        raise DocumentoInvalido('ilegible') from None
    finally:
        libro.close()
    return '\n\n'.join(partes)


def _leer_csv(datos):
    texto = _decodificar(datos)
    muestra = texto[:2048]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=',;\t|')
    except csv.Error:
        dialecto = csv.excel
    try:
        return _filas_a_texto(csv.reader(io.StringIO(texto), dialecto))
    except csv.Error:
        raise DocumentoInvalido('ilegible') from None


# --- Limpieza --------------------------------------------------------------------

_CORREO = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_ENLACE = re.compile(r'\b(?:https?://|www\.)\S+', re.IGNORECASE)
# Siete o mas digitos, aunque vengan separados por espacios, puntos o guiones:
# telefonos, cedulas, NIT, tarjetas, cuentas. Las cantidades y tallas de un
# pedido son mas cortas. Un precio alto tambien se oculta: el Coach cita solo
# los precios del catalogo.
_CIFRA_LARGA = re.compile(r'\+?\d(?:[\s().-]*\d){6,}')


def ocultar_datos_personales(texto):
    texto = _CORREO.sub(OCULTO, texto)
    texto = _ENLACE.sub(OCULTO, texto)
    return _CIFRA_LARGA.sub(OCULTO, texto)


def _normalizar(texto):
    texto = unicodedata.normalize('NFC', texto)
    texto = ''.join(
        c if c in '\n\t' or unicodedata.category(c)[0] != 'C' else ' '
        for c in texto.replace('\r\n', '\n').replace('\r', '\n')
    )
    texto = re.sub(r'[ \t ]+', ' ', texto)
    texto = re.sub(r' ?\n ?', '\n', texto)
    return re.sub(r'\n{3,}', '\n\n', texto).strip()


def _recortar(texto, maximo):
    if len(texto) <= maximo:
        return texto, False
    corte = texto[:maximo]
    espacio = max(corte.rfind(' '), corte.rfind('\n'))
    if espacio > maximo * 0.8:
        corte = corte[:espacio]
    return corte.rstrip(), True


_LECTORES = {'pdf': _leer_pdf, 'xlsx': _leer_xlsx, 'csv': _leer_csv, 'txt': _decodificar}


def leer(datos, nombre=''):
    """`DocumentoLeido` con el extracto listo para el turno, o `DocumentoInvalido`."""
    if not datos:
        raise DocumentoInvalido('vacio')
    if len(datos) > MAX_BYTES_SUBIDA:
        raise DocumentoInvalido('grande')
    formato = detectar_formato(datos, nombre)
    crudo = _LECTORES[formato](datos)[:MAX_LARGO_LECTURA]
    limpio = _normalizar(ocultar_datos_personales(_normalizar(crudo)))
    if len(re.sub(re.escape(OCULTO) + r'|\W', '', limpio)) < 3:
        raise DocumentoInvalido('sin_texto')
    extracto, recortado = _recortar(limpio, MAX_LARGO_EXTRACTO)
    return DocumentoLeido(formato=formato, extracto=extracto, recortado=recortado)
