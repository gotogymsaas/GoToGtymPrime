from django.conf import settings
from django.db import models
from gotogym.ajustes_tienda import coach_habilitado, compras_pausadas, pagos_habilitados


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
    coach_enabled = models.BooleanField(
        default=True,
        help_text="Si está desactivado, Quantum Coach (la IA de GoToGym) no se muestra en la tienda.",
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

    @classmethod
    def coach_habilitado(cls):
        """Igual que las anteriores: sin fila todavia, el Coach esta habilitado."""
        return coach_habilitado()


class AccionDePanel(models.Model):
    """Bitacora de las acciones que el equipo hace en el panel.

    Se escribe desde `require_perms` por cada peticion POST que el permiso
    deja pasar y que no termina en error del servidor o del cliente (4xx/5xx).
    Registra el intento, no su desenlace: muchas vistas rechazan una accion
    con un aviso y una redireccion, y eso tambien queda como una fila. Hoy solo
    se consulta en la base de datos. Guarda quien, que vista y sobre que objeto (los argumentos de la
    URL, como un numero de pedido o un id); no guarda el contenido del
    formulario ni correos, telefonos o documentos, para que la bitacora no
    sea otra copia de datos personales."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    vista = models.CharField(max_length=100)
    argumentos = models.JSONField(default=dict, blank=True)
    codigo_estado = models.PositiveSmallIntegerField()
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada']
        verbose_name = 'Acción del panel'
        verbose_name_plural = 'Acciones del panel'
        indexes = [models.Index(fields=['-creada'], name='accionpanel_creada_idx')]

    def __str__(self):
        return f'{self.vista} {self.argumentos} ({self.creada:%Y-%m-%d %H:%M})'
