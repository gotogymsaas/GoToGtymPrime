from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy
from products.models import ProductVariant


class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = 'pending_payment', gettext_lazy('Pendiente de pago')
    CONFIRMED = 'confirmed', gettext_lazy('Confirmado')
    PREPARING = 'preparing', gettext_lazy('En preparación')
    SHIPPED = 'shipped', gettext_lazy('Enviado')
    IN_TRANSIT = 'in_transit', gettext_lazy('En tránsito')
    DELIVERED = 'delivered', gettext_lazy('Entregado')
    CANCELLED = 'cancelled', gettext_lazy('Cancelado')
    RETURNED = 'returned', gettext_lazy('Devolución')


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', gettext_lazy('Pendiente')
    APPROVED = 'approved', gettext_lazy('Aprobado')
    REJECTED = 'rejected', gettext_lazy('Rechazado')
    CANCELLED = 'cancelled', gettext_lazy('Cancelado')


class DocumentType(models.TextChoices):
    # Mismos valores que `afiliados.models.DocumentType`. Se repiten aqui
    # porque `orders` esta por debajo de `afiliados` en la regla de capas y
    # no puede importarlo.
    CC = 'CC', gettext_lazy('Cédula de ciudadanía')
    CE = 'CE', gettext_lazy('Cédula de extranjería')
    NIT = 'NIT', gettext_lazy('NIT')
    PA = 'PA', gettext_lazy('Pasaporte')
    PPT = 'PPT', gettext_lazy('Permiso por protección temporal (PPT)')
    PEP = 'PEP', gettext_lazy('Permiso especial de permanencia (PEP)')


class CouponDiscountType(models.TextChoices):
    PERCENTAGE = 'percentage', gettext_lazy('Porcentaje')
    FIXED = 'fixed', gettext_lazy('Valor fijo')


class Coupon(models.Model):
    """Cupon de descuento aplicable en el checkout.

    `times_used` se incrementa en `create_order_from_cart` cuando el cupon
    se usa efectivamente; `max_uses` en null significa uso ilimitado.
    """

    code = models.CharField(max_length=30, unique=True)
    discount_type = models.CharField(
        max_length=12, choices=CouponDiscountType.choices, default=CouponDiscountType.PERCENTAGE,
    )
    value = models.DecimalField(max_digits=12, decimal_places=2)
    min_purchase = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    afiliado = models.ForeignKey(
        'afiliados.PerfilAfiliado', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coupons',
        help_text='Si se asigna, las ventas hechas con este cupón se atribuyen a este afiliado.',
    )
    customer_segment = models.ForeignKey(
        'accounts.CustomerSegment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coupons',
        help_text='Si se asigna, solo los clientes de este segmento pueden usar el cupón (precio diferenciado por segmento).',
    )
    # Opt-in explicito: un cupon no se vuelve publico solo por no tener
    # afiliado (el vinculo puede faltar o perderse con SET_NULL).
    coach_can_offer = models.BooleanField(
        default=False,
        help_text='Quantum Coach puede mencionarlo a cualquier visitante. Úsalo solo para cupones de campaña; '
                  'los de afiliados nunca se ofrecen.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(value__gte=0),
                name='coupon_valor_no_negativo',
            ),
            models.CheckConstraint(
                condition=~models.Q(discount_type='percentage') | models.Q(value__lte=100),
                name='coupon_porcentaje_hasta_100',
            ),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        # Los codigos se buscan en mayusculas (ver `get_usable_coupon`): uno
        # guardado en minusculas nunca coincidiria.
        self.code = (self.code or '').strip().upper()
        super().save(*args, **kwargs)

    def is_usable(self, momento=None):
        momento = momento or timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and momento < self.starts_at:
            return False
        if self.ends_at and momento > self.ends_at:
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        return True

    def compute_discount(self, subtotal):
        subtotal = Decimal(subtotal)
        if self.min_purchase is not None and subtotal < self.min_purchase:
            return Decimal('0.00')
        if self.discount_type == CouponDiscountType.PERCENTAGE:
            descuento = subtotal * (self.value / Decimal('100'))
        else:
            descuento = self.value
        descuento = max(Decimal('0.00'), min(descuento, subtotal))
        return descuento.quantize(Decimal('0.01'))


class OrderKind(models.TextChoices):
    PRODUCTS = 'products', gettext_lazy('Productos')
    GIFT_CARD = 'gift_card', gettext_lazy('Tarjeta de regalo')


class Order(models.Model):
    """Pedido persistente.

    El estado logistico (`order_status`) y el estado del pago
    (`payment_status`) son independientes: los controla actor distinto (la
    operacion humana uno, el proveedor de pago el otro) y un pedido puede
    estar pagado y todavia sin alistar.

    `kind` distingue la compra de una tarjeta de regalo: se paga igual que
    cualquier pedido, pero no lleva envio ni stock y no se factura (la venta
    ocurre cuando la tarjeta se canjea, ver `orders.tarjetas_regalo`).

    `total` es lo que se cobra por el proveedor de pago. La parte pagada con
    una tarjeta de regalo va en `gift_card_total` y no es un descuento: el
    valor del pedido sigue siendo `subtotal + shipping_cost - discount_total`.
    """

    kind = models.CharField(max_length=12, choices=OrderKind.choices, default=OrderKind.PRODUCTS)
    # Confirmado sin pago por una cuenta del equipo con el modo de pruebas del
    # panel activo. No se factura, no genera comision y no cuenta como venta.
    is_test_order = models.BooleanField(default=False)
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
    gift_card_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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
    # Idioma en que se hizo el pedido: los correos al cliente salen en ese idioma.
    language = models.CharField(max_length=8, default='es', blank=True)

    # Afiliado cuyo cupon se uso en este pedido, si aplica. Se fija una sola
    # vez al crear el pedido (a partir de `Coupon.afiliado`) y no cambia
    # aunque el cupon se reasigne despues: es la atribucion de esa venta.
    referred_by = models.ForeignKey(
        'afiliados.PerfilAfiliado', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='referred_orders',
    )
    # Cupon aplicado. Sin este vinculo solo se sabia cuanto se descontaba, no
    # cual campana lo origino, y no habia forma de medir el rendimiento de un
    # cupon. Los pedidos anteriores a este campo quedan sin dato (null).
    coupon = models.ForeignKey(
        'orders.Coupon', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders',
    )
    # Tarjeta de regalo con la que se pago parte o todo el pedido.
    gift_card = models.ForeignKey(
        'orders.GiftCard', on_delete=models.PROTECT, null=True, blank=True,
        related_name='redemption_orders',
    )

    # Cuando el pedido paso a entregado. Marca el inicio del periodo de
    # devolucion y, con el, del periodo de validacion de la comision del
    # afiliado. Los pedidos entregados antes de este campo quedan con la fecha
    # de su ultima actualizacion.
    delivered_at = models.DateTimeField(null=True, blank=True)
    # Hitos del pedido. Los anteriores a estos campos quedan sin dato (null):
    # el detalle de cada cambio esta en `OrderStatusHistory` desde que existe.
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Identificacion del comprador para la factura electronica. Opcionales:
    # no todas las compras la piden.
    customer_document_type = models.CharField(max_length=3, choices=DocumentType.choices, blank=True)
    customer_document_number = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['created_at'], name='order_created_at_idx'),
            models.Index(fields=['order_status', 'created_at'], name='order_status_created_idx'),
            models.Index(fields=['payment_status'], name='order_payment_status_idx'),
            models.Index(fields=['email'], name='order_email_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    subtotal__gte=0, shipping_cost__gte=0, discount_total__gte=0, total__gte=0,
                ),
                name='order_importes_no_negativos',
            ),
            models.CheckConstraint(
                condition=models.Q(gift_card_total__gte=0),
                name='order_tarjeta_regalo_no_negativa',
            ),
        ]

    def __str__(self):
        return self.order_number

    @property
    def is_gift_card_purchase(self):
        return self.kind == OrderKind.GIFT_CARD

    @property
    def order_value(self):
        """Valor del pedido antes de descontar lo pagado con tarjeta de regalo:
        lo que se factura."""
        return self.total + self.gift_card_total


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
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name='orderitem_cantidad_positiva'),
            models.CheckConstraint(
                condition=models.Q(unit_price_snapshot__gte=0, line_total__gte=0),
                name='orderitem_importes_no_negativos',
            ),
        ]

    def __str__(self):
        return f"{self.sku_snapshot} x{self.quantity}"


class OrderStatusHistory(models.Model):
    """Registro de cada cambio de estado del pedido: quien lo hizo y cuando.

    `Order.order_status` solo guarda el estado actual; sin esta tabla no hay
    forma de reconstruir el recorrido de un pedido ante un reclamo."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=20, choices=OrderStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=OrderStatus.choices)
    # Vacio si lo hizo el sistema (pago, vencimiento) y no una persona.
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name_plural = 'order status history'

    def __str__(self):
        return f"{self.order.order_number}: {self.from_status or '-'} -> {self.to_status}"


class InvoiceStatus(models.TextChoices):
    PENDING = 'pending', gettext_lazy('Pendiente')
    PROCESSING = 'processing', gettext_lazy('En proceso')
    ISSUED = 'issued', gettext_lazy('Emitida')
    FAILED = 'failed', gettext_lazy('Fallida')


class Invoice(models.Model):
    """Factura electronica de un pedido pagado, emitida en Alegra.

    Solo guarda el rastro de la emision: el documento vive en Alegra. Un
    pedido tiene como maximo una factura; `attempts` y `last_error` dicen por
    que una emision fallida sigue pendiente de reintento.
    """

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='invoice')
    status = models.CharField(
        max_length=12, choices=InvoiceStatus.choices, default=InvoiceStatus.PENDING,
    )
    alegra_contact_id = models.CharField(max_length=40, blank=True)
    alegra_invoice_id = models.CharField(max_length=40, blank=True)
    number = models.CharField(max_length=60, blank=True)
    cufe = models.CharField(max_length=200, blank=True)
    # Respuesta de Alegra tal cual, para reconstruir datos que no se extraigan.
    raw_response = models.JSONField(default=dict, blank=True)

    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['status', 'last_attempt_at'], name='invoice_status_attempt_idx'),
        ]

    def __str__(self):
        return f"{self.order.order_number}: {self.number or self.status}"


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


class GiftCardStatus(models.TextChoices):
    # Creada con su compra, a la espera de que el pago se apruebe: todavia no
    # se puede canjear y el codigo no se ha enviado a nadie.
    PENDING = 'pending', gettext_lazy('Pendiente de pago')
    ACTIVE = 'active', gettext_lazy('Activa')
    # Bloqueada por el equipo (por ejemplo, por un contracargo de la compra).
    DISABLED = 'disabled', gettext_lazy('Bloqueada')
    # La compra no se concreto o se retracto: estado final.
    CANCELLED = 'cancelled', gettext_lazy('Anulada')


class GiftCard(models.Model):
    """Tarjeta de regalo virtual: un saldo canjeable en el checkout.

    No es un cupon. El cupon rebaja el precio; la tarjeta es un medio de pago
    con saldo que se consume por partes. Por eso tiene su propio historial
    (`GiftCardMovement`) y lo pagado con ella va en `Order.gift_card_total`,
    nunca en `discount_total`: la factura del canje sale por el valor
    completo de los productos.

    `code` se guarda normalizado (16 caracteres, sin guiones) y se muestra en
    grupos de cuatro (`display_code`). Vence a los 12 meses de activarse;
    canjearla en parte no prorroga ese plazo.
    """

    code = models.CharField(max_length=16, unique=True)
    status = models.CharField(max_length=12, choices=GiftCardStatus.choices, default=GiftCardStatus.PENDING)
    initial_amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='COP')

    purchase_order = models.OneToOneField(
        Order, on_delete=models.PROTECT, null=True, blank=True, related_name='purchased_gift_card',
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='gift_cards_bought',
    )
    sender_name = models.CharField(max_length=80)
    recipient_name = models.CharField(max_length=80)
    recipient_email = models.EmailField()
    message = models.CharField(max_length=300, blank=True)
    # Idioma en que se compro: el correo al destinatario sale en ese idioma.
    language = models.CharField(max_length=8, default='es', blank=True)

    issued_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    # Ultimo envio exitoso del correo al destinatario.
    sent_at = models.DateTimeField(null=True, blank=True)
    disabled_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['status', 'expires_at'], name='giftcard_status_expires_idx'),
            models.Index(fields=['recipient_email'], name='giftcard_recipient_idx'),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(initial_amount__gt=0), name='giftcard_valor_positivo'),
            models.CheckConstraint(
                condition=models.Q(balance__gte=0, balance__lte=models.F('initial_amount')),
                name='giftcard_saldo_en_rango',
            ),
        ]

    def __str__(self):
        return self.masked_code

    @property
    def display_code(self):
        return '-'.join(self.code[i:i + 4] for i in range(0, len(self.code), 4))

    @property
    def masked_code(self):
        return f'····-{self.code[-4:]}'

    def is_expired(self, momento=None):
        momento = momento or timezone.now()
        return self.expires_at is not None and momento > self.expires_at

    def is_usable(self, momento=None):
        return (
            self.status == GiftCardStatus.ACTIVE
            and self.balance > 0
            and not self.is_expired(momento)
        )

    @property
    def is_unused(self):
        """Nunca se ha canjeado, ni siquiera en un pedido que luego se cancelo
        y devolvio el saldo: es la condicion para aceptar el retracto."""
        return not self.movements.filter(kind=GiftCardMovementKind.REDEEM).exists()


class GiftCardMovementKind(models.TextChoices):
    ISSUE = 'issue', gettext_lazy('Emisión')
    REDEEM = 'redeem', gettext_lazy('Canje')
    RELEASE = 'release', gettext_lazy('Devolución de saldo')
    VOID = 'void', gettext_lazy('Anulación')


class GiftCardMovement(models.Model):
    """Cada cambio del saldo de una tarjeta, con el pedido que lo causo.

    `amount` lleva signo: positivo suma saldo (emision, devolucion), negativo
    lo resta (canje, anulacion). `balance_after` es el saldo que quedo; con
    ambos se reconstruye la historia completa ante un reclamo."""

    gift_card = models.ForeignKey(GiftCard, on_delete=models.CASCADE, related_name='movements')
    kind = models.CharField(max_length=10, choices=GiftCardMovementKind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, null=True, blank=True, related_name='gift_card_movements',
    )
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.gift_card.masked_code}: {self.kind} {self.amount}'
