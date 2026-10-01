from django.conf import settings
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


class InventoryAdjustmentReason(models.TextChoices):
    MANUAL = 'manual', 'Ajuste manual'
    SALE = 'sale', 'Venta'
    RESTOCK = 'restock', 'Reposicion (cancelacion o devolucion)'


class InventoryAdjustment(models.Model):
    """Kardex: registro historico de cada cambio de stock, no solo el valor
    final que ya guarda `Inventory` (P02: "ajustes con historial" en
    Shopify/Adobe/Salesforce/BigCommerce/WooCommerce)."""

    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='adjustments')
    delta = models.IntegerField(help_text="Positivo si suma stock, negativo si lo descuenta.")
    quantity_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=InventoryAdjustmentReason.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text="Vacio si el ajuste lo disparo el sistema (venta o reposicion), no una persona.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        signo = '+' if self.delta >= 0 else ''
        return f"{self.inventory.variant.sku}: {signo}{self.delta} ({self.reason})"
