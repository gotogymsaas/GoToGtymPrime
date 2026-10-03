import secrets
import string
from decimal import Decimal

from django.conf import settings
from django.db import models


def generate_referral_code():
    """Codigo corto y legible: sirve a la vez como identificador del
    afiliado y, una vez aprobado, como `Coupon.code` que sus seguidores
    usan en el checkout (ver patron de "codigo como objeto de
    integracion" entre panel admin y panel de afiliados)."""
    alfabeto = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(8))


class InfluencerStatus(models.TextChoices):
    PENDING = 'pending', 'Pendiente de revision'
    APPROVED = 'approved', 'Aprobado'
    REJECTED = 'rejected', 'Rechazado'


class InfluencerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='influencer_profile')
    referral_code = models.CharField(max_length=36, unique=True, default=generate_referral_code)
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Tasa propia de este afiliado. Vacio usa la tasa global del programa.",
    )
    commission_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_referred = models.PositiveIntegerField(default=0)
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    # `is_active=True` de fabrica preserva el comportamiento de los perfiles
    # que ya existian antes de introducir el flujo de aprobacion (ver
    # `status` mas abajo): para ellos no hay una migracion de datos que
    # adivine su estado, asi que el valor por defecto los deja como ya
    # estaban. La vista `suscribete` sobreescribe esto explicitamente a
    # PENDING para toda solicitud nueva.
    is_active = models.BooleanField(default=True)

    status = models.CharField(
        max_length=12, choices=InfluencerStatus.choices, default=InfluencerStatus.APPROVED,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # Consentimiento a los terminos del programa y a la obligacion de
    # divulgacion publicitaria (FTC, 2023; SIC, 2020), registrado en cada
    # solicitud o re-solicitud (ver `influencer.views.suscribete`).
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Influencer: {self.user.email} ({self.referral_code})"


class InfluencerProgramSettings(models.Model):
    """Configuracion global del programa de afiliados (fila unica, mismo
    patron que `administracion.PanelSettings`)."""

    default_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        help_text="Porcentaje que gana el afiliado sobre el neto del pedido, si el afiliado no tiene una tasa propia.",
    )
    default_customer_discount = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        help_text="Porcentaje de descuento que recibe el cliente final al usar el codigo de un afiliado nuevo.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuracion del programa de afiliados"
        verbose_name_plural = "Configuracion del programa de afiliados"

    def __str__(self):
        return "Configuracion del programa de afiliados"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class WithdrawalStatus(models.TextChoices):
    PENDING = 'pending', 'Pendiente'
    PAID = 'paid', 'Pagada'
    REJECTED = 'rejected', 'Rechazada'


class WithdrawalRequest(models.Model):
    """Solicitud de pago de comisiones. Al crearse, "reserva" las comisiones
    aprobadas y aun no ligadas a otra solicitud (ver `services.request_withdrawal`):
    el monto queda fijo aunque despues se aprueben mas comisiones."""

    influencer = models.ForeignKey(InfluencerProfile, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=WithdrawalStatus.choices, default=WithdrawalStatus.PENDING)
    # Texto libre que escribe el afiliado al solicitar: numero de cuenta e
    # indicaciones de pago. Es un dato financiero: solo lo ve el personal.
    payment_details = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"Retiro {self.influencer.user.email}: ${self.amount}"


class CommissionStatus(models.TextChoices):
    PENDING = 'pending', 'Pendiente'
    APPROVED = 'approved', 'Aprobada'
    PAID = 'paid', 'Pagada'
    REVERTED = 'reverted', 'Revertida'


class Commission(models.Model):
    """Comision de un pedido referido, con el ciclo de vida documentado en
    el benchmarking (P10): pendiente al aprobarse el pago, aprobada cuando
    el pedido llega a entregado (ya paso la ventana de devolucion),
    revertida si el pedido se cancela o se devuelve, y pagada cuando se
    liquida una solicitud de retiro que la incluye."""

    influencer = models.ForeignKey(InfluencerProfile, on_delete=models.CASCADE, related_name='commissions')
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='commission')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=CommissionStatus.choices, default=CommissionStatus.PENDING)
    withdrawal_request = models.ForeignKey(
        WithdrawalRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='commissions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comision {self.order.order_number}: ${self.amount} ({self.status})"


class ReferralClick(models.Model):
    """Un uso del enlace de referido (`?ref=<codigo>`) de un afiliado.

    Se registra una sola vez por sesion y por codigo (ver
    `influencer.middleware.ReferralTrackingMiddleware`), para que recargar
    la pagina no infle el conteo. Junto con `total_referred` permite una
    metrica basica de conversion (ventas / clics) sin necesitar un sistema
    de analitica propio."""

    influencer = models.ForeignKey(InfluencerProfile, on_delete=models.CASCADE, related_name='referral_clicks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Clic de {self.influencer.referral_code} ({self.created_at:%Y-%m-%d %H:%M})"
