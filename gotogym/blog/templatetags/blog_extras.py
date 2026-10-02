import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_CITA = re.compile(r'\[(\d{1,2})\]')
_NEGRITA = re.compile(r'\*\*(.+?)\*\*')


def _en_linea(texto):
    """Escapa el texto y convierte `**negrita**` y las citas `[n]`.

    Se escapa primero y se marca como seguro despues: el contenido lo
    escribe quien edita el Journal, pero nunca debe poder inyectar HTML.
    """
    texto = escape(texto)
    texto = _NEGRITA.sub(r'<strong>\1</strong>', texto)
    return _CITA.sub(
        r'<sup class="cite"><a href="#ref-\1" aria-label="Referencia \1">[\1]</a></sup>',
        texto,
    )


@register.filter
def post_body(value):
    """Cuerpo de una entrada del Journal.

    Texto plano con tres convenciones, para no depender de HTML:
    - una linea `## Titulo` es un subtitulo;
    - un bloque donde todas las lineas empiezan con `- ` es una lista;
    - cualquier otro bloque (separado por una linea en blanco) es un parrafo.
    """
    bloques = re.split(r'\n\s*\n', (value or '').replace('\r\n', '\n').strip())
    salida = []
    for bloque in bloques:
        lineas = [linea.strip() for linea in bloque.split('\n') if linea.strip()]
        if not lineas:
            continue
        if len(lineas) == 1 and lineas[0].startswith('## '):
            salida.append(f'<h2>{_en_linea(lineas[0][3:])}</h2>')
        elif all(linea.startswith('- ') for linea in lineas):
            items = ''.join(f'<li>{_en_linea(linea[2:])}</li>' for linea in lineas)
            salida.append(f'<ul>{items}</ul>')
        else:
            salida.append(f'<p>{"<br>".join(_en_linea(linea) for linea in lineas)}</p>')
    return mark_safe('\n'.join(salida))
