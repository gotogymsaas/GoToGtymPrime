"""Utilidades de SEO: datos estructurados (JSON-LD) y textos para metadatos.

El JSON-LD se escribe dentro de una etiqueta `<script>`, asi que el contenido
(que incluye nombres y descripciones editables desde el panel) se escapa para
que un texto como `</script>` no pueda cerrar la etiqueta ni inyectar HTML.
"""
import json
import re

from django.utils.safestring import mark_safe

_ESCAPES = {ord('<'): '\\u003C', ord('>'): '\\u003E', ord('&'): '\\u0026'}


def json_ld(datos):
    """Serializa a JSON seguro para incrustar en un `<script type="application/ld+json">`."""
    return mark_safe(json.dumps(datos, ensure_ascii=False).translate(_ESCAPES))


def recortar(texto, largo=155):
    """Resumen de una linea para `meta description`: sin saltos ni espacios
    repetidos y cortado en una palabra completa."""
    limpio = re.sub(r'\s+', ' ', str(texto or '')).strip()
    if len(limpio) <= largo:
        return limpio
    corte = limpio[: largo - 1].rsplit(' ', 1)[0].rstrip(',;:.-')
    return corte + '…'


def url_absoluta(request, ruta):
    """URL completa de una ruta o de un archivo (`/media/...`)."""
    return request.build_absolute_uri(ruta)


def contexto_seo(titulo, descripcion, *, tipo='website', imagen=None, datos=None):
    """Datos que la plantilla base imprime como metadatos (descripcion, Open
    Graph) y como JSON-LD. Una sola fuente por pagina: la descripcion sirve a
    la vez para el buscador y para las vistas previas al compartir."""
    contexto = {'seo_title': titulo, 'seo_description': recortar(descripcion), 'seo_type': tipo}
    if imagen:
        contexto['seo_image'] = imagen
    if datos:
        contexto['seo_json_ld'] = json_ld(datos)
    return contexto
