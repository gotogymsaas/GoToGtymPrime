from django.contrib import admin

from .models import EventoAnalitica


@admin.register(EventoAnalitica)
class EventoAnaliticaAdmin(admin.ModelAdmin):
    """Solo lectura: los eventos los escribe el sitio, no una persona.

    Editarlos a mano invalidaria cualquier comparacion posterior, que es
    justo para lo que existe la tabla.
    """

    list_display = ('nombre', 'ruta', 'autenticado', 'creado')
    list_filter = ('nombre', 'autenticado', 'creado')
    search_fields = ('ruta',)
    date_hierarchy = 'creado'
    readonly_fields = ('nombre', 'ruta', 'sesion', 'autenticado', 'propiedades', 'creado')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
