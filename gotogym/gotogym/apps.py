from django.contrib.admin.apps import AdminConfig


class SitioAdminConfig(AdminConfig):
    """Reemplaza al administrador de Django por `gotogym.admin_site.SitioAdmin`."""

    default_site = 'gotogym.admin_site.SitioAdmin'
