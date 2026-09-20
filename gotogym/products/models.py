from django.db import models


class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    """Ficha comercial. La unidad vendible es ProductVariant, no este modelo.

    `discount` y `stock` se conservan por compatibilidad con datos existentes,
    pero el stock real por talla/color vive a nivel de variante.
    """

    name = models.CharField(max_length=150)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=4)
    discount = models.PositiveIntegerField(default=0, help_text="Porcentaje de descuento")
    stock = models.PositiveIntegerField(default=0)
    featured = models.BooleanField(default=False)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    def __str__(self):
        return self.name

    @property
    def primary_image(self):
        """Imagen a mostrar: la marcada como principal, si no la primera
        media, si no la imagen heredada del propio producto."""
        media = list(self.media.all())
        principal = next((m for m in media if m.is_primary), None) or (media[0] if media else None)
        if principal and principal.image:
            return principal.image
        return self.image or None


class ProductVariant(models.Model):
    """Unidad vendible: una combinacion concreta de talla y color."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=64, unique=True)
    size = models.CharField(max_length=20)
    color = models.CharField(max_length=60)
    price_override = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Si se define, reemplaza el precio base del producto.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['product_id', 'size', 'color']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'size', 'color'],
                name='unique_variant_per_product_size_color',
            ),
        ]

    def __str__(self):
        return f"{self.sku} - {self.product.name} ({self.size}/{self.color})"

    @property
    def effective_price(self):
        if self.price_override is not None:
            return self.price_override
        return self.product.base_price


class ProductMedia(models.Model):
    """Imagen asociada a un producto y, opcionalmente, a una variante concreta."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='media')
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name='media',
    )
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.product.name} - {self.image.name}"
