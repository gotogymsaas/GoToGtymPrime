"""Documento de identidad del comprador: limpieza y validacion.

Lo usan el checkout y el perfil de la cuenta, para que un mismo documento se
acepte (o rechace) igual en los dos sitios y llegue a la factura sin
formato (sin puntos, espacios ni el digito de verificacion del NIT).
"""
import re

from django.utils.translation import gettext

from .models import DocumentType

NUMERO_SOLO_DIGITOS = re.compile(r'^\d{5,15}$')
NUMERO_ALFANUMERICO = re.compile(r'^[A-Za-z0-9]{4,20}$')


def limpiar_numero(tipo, numero):
    """Deja solo los caracteres del numero: `900.123.456-8` (NIT) -> `900123456`."""
    numero = (numero or '').strip()
    if tipo == DocumentType.NIT:
        numero = numero.split('-')[0]
    return re.sub(r'[\s.\-]', '', numero)


def error_de_documento(tipo, numero):
    """Devuelve `(campo, mensaje)` si el par tipo/numero no es valido, o None.

    Ambos vacios es valido: el documento es opcional. Llega ya limpio con
    `limpiar_numero`.
    """
    if numero and not tipo:
        return 'document_type', gettext('Selecciona el tipo de documento.')
    if tipo and not numero:
        return 'document_number', gettext('Escribe el número de documento.')
    if tipo in (DocumentType.CC, DocumentType.NIT) and not NUMERO_SOLO_DIGITOS.match(numero):
        return 'document_number', gettext('Escribe solo números, entre 5 y 15 dígitos.')
    if tipo and not NUMERO_ALFANUMERICO.match(numero):
        return 'document_number', gettext('Escribe un número de documento válido.')
    return None
