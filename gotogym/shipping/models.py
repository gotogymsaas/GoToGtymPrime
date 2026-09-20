from django.db import models

from orders.models import Order


class ShippingQuote(models.Model):
    """Cotizacion de envio de un pedido.

    El costo aqui es el mismo que se guarda en `Order.shipping_cost`: una
    sola fuente de verdad, no dos numeros que puedan divergir.
    """

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipping_quote')

    carrier_name = models.CharField(max_length=80)
    method_name = models.CharField(max_length=80)
    cost = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_days = models.PositiveIntegerField()
    tracking_code = models.CharField(max_length=64, blank=True)
    shipping_status = models.CharField(max_length=20, default='pending')

    def __str__(self):
        return f"{self.order.order_number} · {self.carrier_name} · ${self.cost}"
