from django.conf import settings
from django.http import HttpRequest


def journal_visibility(request: HttpRequest) -> dict[str, bool]:
    """Indica si el Journal debe ser visible en la interfaz y navegación.

    En modo 'shadow' (False por defecto), la app y sus contenidos siguen
    existiendo y funcionando, pero la sección no se despliega en los menús
    ni llamadas a la acción de cara al usuario.
    """
    return {
        'journal_visible': getattr(settings, 'JOURNAL_VISIBLE', False),
    }
