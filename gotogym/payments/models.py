from django.db import models

from orders.models import Order


class PaymentTransaction(models.Model):
    """Un intento de pago sobre un pedido.

    Los campos `preference_id`/`payment_id`/`external_reference` existen
    desde ya aunque el unico proveedor sea el simulado: son los que un
    proveedor real necesita, y evitan tener que rehacer el modelo cuando se
    integre uno.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        APPROVED = 'approved', 'Aprobado'
        REJECTED = 'rejected', 'Rechazado'
        CANCELLED = 'cancelled', 'Cancelado'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_transactions')

    provider = models.CharField(max_length=30)
    preference_id = models.CharField(max_length=100, blank=True)
    payment_id = models.CharField(max_length=100, blank=True)
    external_reference = models.CharField(max_length=64)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='COP')

    idempotency_key = models.CharField(max_length=64, unique=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order.order_number} · {self.provider} · {self.status}"
