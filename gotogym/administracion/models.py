from django.db import models


class PanelSettings(models.Model):
    """Configuracion global del panel admin.

    Fila unica (singleton via `load()`): no tiene sentido tener mas de una
    configuracion vigente al mismo tiempo. El permiso automatico que Django
    crea para este modelo (`administracion.change_panelsettings`) es el que
    protege la seccion "Configuracion" del panel.
    """

    low_stock_threshold = models.PositiveIntegerField(
        default=5, help_text="A partir de cuantas unidades una variante se marca como 'stock bajo'.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracion del panel"
        verbose_name_plural = "Configuracion del panel"

    def __str__(self):
        return "Configuracion del panel"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
