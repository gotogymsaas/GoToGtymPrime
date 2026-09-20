from django.db import models

from products.models import ProductVariant


class Inventory(models.Model):
    """Stock disponible de una variante. Tabla separada de ProductVariant
    para poder bloquear filas de escritura frecuente (descuento de stock)
    sin afectar las lecturas de catalogo."""

    variant = models.OneToOneField(ProductVariant, on_delete=models.CASCADE, related_name='inventory')
    quantity_available = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.variant.sku}: {self.quantity_available} disponibles"
