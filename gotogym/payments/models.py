from django.conf import settings
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


class Refund(models.Model):
    """Reembolso real de una transaccion ya aprobada, disparado desde el
    panel admin (ver `payments.services.refund_order_payment`).

    Reemplaza a la nota manual en `Order.internal_note` que existia antes
    para el caso "pago aprobado, sin stock" -- ahora ese caso, y cualquier
    cancelacion o devolucion con pago aprobado, puede resolverse
    devolviendo el dinero de verdad a traves del proveedor de pago."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        APPROVED = 'approved', 'Aprobado'
        FAILED = 'failed', 'Fallido'

    payment_transaction = models.ForeignKey(
        PaymentTransaction, on_delete=models.CASCADE, related_name='refunds',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    provider_refund_id = models.CharField(max_length=100, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Reembolso {self.payment_transaction.order.order_number}: ${self.amount} ({self.status})"
