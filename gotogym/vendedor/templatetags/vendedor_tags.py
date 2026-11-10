"""Seccion de personalizacion con Quantum Coach para Mi cuenta.

Es un inclusion tag para que `accounts` no tenga que importar `vendedor`
(la regla de capas lo impide): la plantilla del perfil solo la carga.
"""
from django import template

from .. import personalizacion

register = template.Library()


@register.inclusion_tag("vendedor/_personalizacion.html", takes_context=True)
def personalizacion_coach(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"mostrar": False}
    return {"mostrar": True, "csrf_token": context.get("csrf_token"), **personalizacion.contexto(user)}
