from django.conf import settings
from django.db import models

from products.models import ProductVariant


class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = 'pending_payment', 'Pendiente de pago'
    CONFIRMED = 'confirmed', 'Confirmado'
    PREPARING = 'preparing', 'En preparacion'
    SHIPPED = 'shipped', 'Enviado'
    IN_TRANSIT = 'in_transit', 'En transito'
    DELIVERED = 'delivered', 'Entregado'
    CANCELLED = 'cancelled', 'Cancelado'


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pendiente'
    APPROVED = 'approved', 'Aprobado'
    REJECTED = 'rejected', 'Rechazado'
    CANCELLED = 'cancelled', 'Cancelado'


class Order(models.Model):
    """Pedido persistente.

    El estado logistico (`order_status`) y el estado del pago
    (`payment_status`) son independientes: los controla actor distinto (la
    operacion humana uno, el proveedor de pago el otro) y un pedido puede
    estar pagado y todavia sin alistar.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders',
    )
    order_number = models.CharField(max_length=32, unique=True)

    email = models.EmailField()
    phone = models.CharField(max_length=40)

    currency = models.CharField(max_length=3, default='COP')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    order_status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING_PAYMENT,
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING,
    )

    # Nota operativa para casos que exigen revision humana, como un pago
    # aprobado sin stock suficiente para cumplirlo. No es visible al cliente.
    internal_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    """Linea de pedido con copia de los datos del producto.

    Los campos `*_snapshot` congelan lo que se vendio: si luego cambia el
    precio o se desactiva la variante, el historico del pedido no cambia.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items',
    )

    product_name_snapshot = models.CharField(max_length=150)
    sku_snapshot = models.CharField(max_length=64)
    size_snapshot = models.CharField(max_length=20)
    color_snapshot = models.CharField(max_length=60)
    unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)

    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.sku_snapshot} x{self.quantity}"


class Address(models.Model):
    """Direccion de entrega del pedido."""

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='address')

    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=40)
    country = models.CharField(max_length=80)
    department = models.CharField(max_length=80)
    city = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=20, blank=True)
    address_line = models.CharField(max_length=255)
    address_complement = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name} - {self.city}"
