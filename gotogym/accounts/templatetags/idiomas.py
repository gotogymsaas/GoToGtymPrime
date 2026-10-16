from django import template
from django.urls import translate_url
from django.utils.translation import gettext

register = template.Library()


@register.simple_tag(takes_context=True)
def url_en_idioma(context, codigo):
    """La direccion de la pagina actual (con su consulta) en otro idioma.

    Se calcula al dibujar la pagina, cuando el idioma activo es el de la URL
    que se esta mostrando: `translate_url` solo sabe leer direcciones del
    idioma activo. Una direccion que no lleva prefijo de idioma se devuelve
    sin cambios.
    """
    return translate_url(context['request'].get_full_path(), codigo)


@register.filter
def traducir(valor):
    """Traduce un texto que viene de la base de datos (nombre, descripcion, categoria, color...).

    El catalogo de traducciones hace de diccionario: la clave es el texto
    tal como esta guardado. Si no hay traduccion, se muestra igual.
    """
    return gettext(valor) if isinstance(valor, str) and valor else valor
