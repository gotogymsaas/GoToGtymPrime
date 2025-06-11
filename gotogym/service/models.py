from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    """Entidad corporativa que puede gestionar varias marcas."""

    name = models.CharField(max_length=255,verbose_name=_("Nombre de la empresa"),)
    identifier = models.CharField(max_length=100,unique=True,db_index=True,verbose_name=_("Identificador único"),help_text=_("Ej.: NIT, CIF, CUIT o cualquier ID interno"),)
    administrators = models.ManyToManyField(settings.AUTH_USER_MODEL,related_name="managed_companies",verbose_name=_("Administradores"),)
    created_at = models.DateTimeField( auto_now_add=True,verbose_name=_("Fecha de creación"),)
    updated_at = models.DateTimeField(auto_now=True,verbose_name=_("Última actualización"),)

    class Meta:
        verbose_name = _("Empresa")
        verbose_name_plural = _("Empresas")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["name"]),]

    def __str__(self) -> str:
        return self.name


class Brand(models.Model):
    """Marca (línea de producto) asociada a una Company."""

    company = models.ForeignKey(Company,on_delete=models.CASCADE,related_name="brands",verbose_name=_("Empresa"),)
    name = models.CharField( max_length=255, verbose_name=_("Nombre de la marca"), )
    logo = models.ImageField( upload_to="brands/logos/", null=True, blank=True, verbose_name=_("Logotipo"), )
    description = models.TextField( null=True, blank=True, verbose_name=_("Descripción de la marca"),)
    created_at = models.DateTimeField(auto_now_add=True,verbose_name=_("Fecha de creación"),)
    updated_at = models.DateTimeField(auto_now=True,verbose_name=_("Última actualización"),)

    class Meta:
        verbose_name = _("Marca")
        verbose_name_plural = _("Marcas")
        ordering = ("name",)
        unique_together = ("company", "name")  

    def __str__(self) -> str:
        return f"{self.name} ({self.company.name})"
