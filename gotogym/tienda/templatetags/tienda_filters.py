from django import template

register = template.Library()


@register.filter
def cop(value):
    """Formatea un monto en pesos colombianos: separador de miles con
    punto, sin decimales (ej. 400000 -> "400.000"). Independiente del
    idioma activo del sitio: COP siempre se muestra igual, en /es/ o /en/.
    """
    try:
        amount = int(round(float(value)))
    except (TypeError, ValueError):
        return value
    return f"{amount:,}".replace(",", ".")
