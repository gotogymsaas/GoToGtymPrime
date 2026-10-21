from django.db import models
from gotogym.ajustes_tienda import compras_pausadas, pagos_habilitados


class PanelSettings(models.Model):
    """Configuracion global del panel admin.

    Fila unica (singleton via `load()`): no tiene sentido tener mas de una
    configuracion vigente al mismo tiempo. El permiso automatico que Django
    crea para este modelo (`administracion.change_panelsettings`) es el que
    protege la seccion "Configuracion" del panel.
    """

    low_stock_threshold = models.PositiveIntegerField(
        default=5, help_text="A partir de cuántas unidades una variante se marca como 'stock bajo'.",
    )
    monthly_sales_goal = models.PositiveIntegerField(
        default=0,
        help_text="Meta de ingresos (COP) para el rango de fechas consultado en el panel. 0 desactiva la barra de progreso.",
    )
    purchases_paused = models.BooleanField(
        default=False,
        help_text="Si está activo, la tienda no deja agregar al carrito ni crear pedidos nuevos. El stock no se modifica.",
    )
    purchases_paused_at = models.DateTimeField(null=True, blank=True)
    online_payments_enabled = models.BooleanField(
        default=True,
        help_text="Si está desactivado, el checkout no abre pagos nuevos con Mercado Pago. Los pagos ya iniciados se siguen confirmando.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración del panel"
        verbose_name_plural = "Configuración del panel"

    def __str__(self):
        return "Configuración del panel"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def compras_pausadas(cls):
        """Lectura liviana (sin crear la fila) para consultar en cada
        peticion de la tienda."""
        return compras_pausadas()

    @classmethod
    def pagos_habilitados(cls):
        """Igual que `compras_pausadas`: sin fila todavia, los pagos estan
        habilitados (el valor por defecto)."""
        return pagos_habilitados()
