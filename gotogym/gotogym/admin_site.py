"""Administrador de Django restringido.

El panel de trabajo diario es `/admin-panel/` (personal con permisos). El
administrador de Django da acceso directo a los datos, asi que se limita a
superusuarios y se protege su formulario de acceso contra intentos repetidos.
Ademas su ruta se puede cambiar con la variable `ADMIN_URL`.
"""
from django.contrib import admin

from .ratelimit import rate_limit


class SitioAdmin(admin.AdminSite):
    def has_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    def login(self, request, extra_context=None):
        # Cuenta solo los envios del formulario: 10 intentos cada 5 minutos.
        limitado = rate_limit('admin_login', limit=10, period_seconds=300, metodos=('POST',))(
            lambda peticion: super(SitioAdmin, self).login(peticion, extra_context)
        )
        return limitado(request)
