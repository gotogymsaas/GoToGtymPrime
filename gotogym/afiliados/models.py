import secrets
import string
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone


def generate_referral_code():
    """Codigo corto y legible: sirve a la vez como identificador del
    afiliado y, una vez aprobado, como `Coupon.code` que sus seguidores
    usan en el checkout (ver patron de "codigo como objeto de
    integracion" entre panel admin y panel de afiliados)."""
    alfabeto = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(8))


class EstadoAfiliado(models.TextChoices):
    PENDING = 'pending', 'Pendiente de revision'
    APPROVED = 'approved', 'Aprobado'
    REJECTED = 'rejected', 'Rechazado'


class DocumentType(models.TextChoices):
    CC = 'CC', 'Cedula de ciudadania'
    CE = 'CE', 'Cedula de extranjeria'
    NIT = 'NIT', 'NIT'
    PA = 'PA', 'Pasaporte'
    PPT = 'PPT', 'Permiso por proteccion temporal (PPT)'
    PEP = 'PEP', 'Permiso especial de permanencia (PEP)'


class MotivoSalida(models.TextChoices):
    VOLUNTARY = 'voluntary', 'Baja solicitada por el afiliado'
    FRAUD = 'fraud', 'Fraude o uso indebido del codigo'
    BREACH = 'breach', 'Incumplimiento de los terminos'
    INACTIVITY = 'inactivity', 'Inactividad prolongada'
    OTHER = 'other', 'Otro'


class PerfilAfiliado(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_afiliado')
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
        max_length=12, choices=EstadoAfiliado.choices, default=EstadoAfiliado.APPROVED,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # Consentimiento a los terminos del programa y a la obligacion de
    # divulgacion publicitaria (FTC, 2023; SIC, 2020), registrado en cada
    # solicitud o re-solicitud (ver `afiliados.views.suscribete`).
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    # Version del texto aceptado (ver `afiliados.terminos`). Vacio en los
    # perfiles anteriores a que se registrara: aceptaron una version previa.
    terms_version = models.CharField(max_length=20, blank=True)

    # Datos personales de la postulacion: el equipo necesita saber quien es
    # la persona detras de la marca antes de aprobarla. Vacios en los
    # perfiles anteriores a que se pidieran (`blank=True`, sin migracion de
    # datos que los invente).
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=255, blank=True)
    document_type = models.CharField(max_length=3, choices=DocumentType.choices, blank=True)
    document_number = models.CharField(max_length=20, blank=True)

    # Revision de la postulacion: las notas son internas (el postulante no las
    # ve); el motivo de rechazo si se le comunica.
    review_notes = models.TextField(blank=True)
    rejection_reason = models.CharField(max_length=500, blank=True)

    # Salida del programa. La baja voluntaria exige un preaviso: se registra
    # cuando se solicita (`exit_requested_at`) y se hace efectiva en
    # `exit_effective_at`; hasta entonces el codigo y el panel siguen activos.
    # `exited_at` es cuando dejo de estar activo, por cualquier causa.
    exit_requested_at = models.DateTimeField(null=True, blank=True)
    exit_effective_at = models.DateTimeField(null=True, blank=True)
    exited_at = models.DateTimeField(null=True, blank=True)
    exit_reason = models.CharField(max_length=12, choices=MotivoSalida.choices, blank=True)
    exit_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Perfil de afiliado"
        verbose_name_plural = "Perfiles de afiliado"

    def __str__(self):
        return f"Afiliado: {self.user.email} ({self.referral_code})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self):
        """Como se nombra a la persona en pantalla: el nombre que dio al
        postularse, el de su cuenta, o su correo si no hay ninguno."""
        return self.full_name or self.user.get_full_name() or self.user.email

    @property
    def baja_solicitada(self):
        return self.is_active and self.exit_requested_at is not None


class SocialPlatform(models.TextChoices):
    INSTAGRAM = 'instagram', 'Instagram'
    TIKTOK = 'tiktok', 'TikTok'
    YOUTUBE = 'youtube', 'YouTube'
    FACEBOOK = 'facebook', 'Facebook'
    X = 'x', 'X (Twitter)'
    TWITCH = 'twitch', 'Twitch'
    LINKEDIN = 'linkedin', 'LinkedIn'
    PINTEREST = 'pinterest', 'Pinterest'
    OTHER = 'other', 'Otra'


URL_DE_PERFIL = {
    SocialPlatform.INSTAGRAM: 'https://www.instagram.com/{usuario}/',
    SocialPlatform.TIKTOK: 'https://www.tiktok.com/@{usuario}',
    SocialPlatform.YOUTUBE: 'https://www.youtube.com/@{usuario}',
    SocialPlatform.FACEBOOK: 'https://www.facebook.com/{usuario}',
    SocialPlatform.X: 'https://x.com/{usuario}',
    SocialPlatform.TWITCH: 'https://www.twitch.tv/{usuario}',
    SocialPlatform.LINKEDIN: 'https://www.linkedin.com/in/{usuario}',
    SocialPlatform.PINTEREST: 'https://www.pinterest.com/{usuario}/',
}


class SocialNetwork(models.Model):
    """Una red social del afiliado con su usuario y audiencia declarada.

    Es lo que el equipo mira para decidir si aprueba la postulacion. El numero
    de seguidores lo declara la persona: no se verifica contra la red."""

    afiliado = models.ForeignKey(PerfilAfiliado, on_delete=models.CASCADE, related_name='social_networks')
    platform = models.CharField(max_length=12, choices=SocialPlatform.choices)
    # Nombre de la red cuando `platform` es "Otra".
    other_name = models.CharField(max_length=60, blank=True)
    username = models.CharField(max_length=60)
    followers = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.platform_label}: @{self.username} ({self.followers})"

    @property
    def platform_label(self):
        if self.platform == SocialPlatform.OTHER and self.other_name:
            return self.other_name
        return self.get_platform_display()

    @property
    def profile_url(self):
        """Enlace al perfil, para que quien revisa lo abra de un clic. Vacio
        en "Otra": no hay forma de saber donde vive ese usuario."""
        plantilla = URL_DE_PERFIL.get(self.platform)
        return plantilla.format(usuario=self.username) if plantilla else ''


class PayoutAccount(models.Model):
    """Cuenta Bre-B donde se le paga al afiliado, con la identidad del
    titular para poder asociar cada pago a una persona concreta.

    Bre-B (Banco de la Republica) mueve el dinero a una *llave* que el
    titular registro en su banco o billetera: documento, celular, correo o
    un codigo alfanumerico (que lleva "@"). No se pregunta de que tipo es: el
    afiliado la escribe tal como la creo en su banco. La llave no basta para saber a quien se paga, de
    ahi el nombre, el documento y el contacto. Son datos personales y
    financieros: solo los ve el propio afiliado y el personal del panel."""

    afiliado = models.OneToOneField(PerfilAfiliado, on_delete=models.CASCADE, related_name='payout_account')
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=40)
    address = models.CharField(max_length=255)
    document_type = models.CharField(max_length=3, choices=DocumentType.choices)
    document_number = models.CharField(max_length=20)
    breb_key = models.CharField(max_length=80)
    # Consentimiento a los terminos del pago por Bre-B y a la autorizacion de
    # tratamiento de datos personales (Ley 1581 de 2012), registrado cada vez
    # que el afiliado guarda su cuenta (ver `afiliados.views.cuenta_de_pago`).
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    data_consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cuenta Bre-B de {self.afiliado.user.email}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def documento_coincide_con_el_perfil(self):
        """Los terminos piden que la cuenta sea del afiliado. Si el perfil
        todavia no tiene documento (postulacion anterior a que se pidiera),
        no hay con que comparar y no se advierte."""
        perfil = self.afiliado
        if not perfil.document_number:
            return True
        return (
            self.document_type == perfil.document_type
            and self.document_number.upper() == perfil.document_number.upper()
        )

    def as_payment_details(self):
        """Copia en texto de los datos de pago, para fijarla en la solicitud
        de comision: si el afiliado cambia su cuenta despues, un pago ya
        solicitado conserva a donde se iba a enviar."""
        return (
            f"Llave Bre-B: {self.breb_key}\n"
            f"Titular: {self.full_name}\n"
            f"Documento: {self.document_type} {self.document_number}\n"
            f"Telefono: {self.phone}\n"
            f"Direccion: {self.address}"
        )


class ConfiguracionProgramaAfiliados(models.Model):
    """Configuracion global del programa de afiliados (fila unica, mismo
    patron que `administracion.PanelSettings`)."""

    default_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20.00'),
        help_text="Porcentaje que gana el afiliado sobre el subtotal del pedido, si el afiliado no tiene una tasa propia.",
    )
    default_customer_discount = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        help_text="Porcentaje de descuento que recibe el cliente final al usar el codigo de un afiliado nuevo.",
    )
    minimum_payout = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('100000.00'),
        help_text="Monto minimo de comisiones confirmadas para poder solicitar un pago.",
    )
    inactivity_days = models.PositiveIntegerField(
        default=90,
        help_text="Dias sin clics ni ventas a partir de los cuales un afiliado se lista como inactivo.",
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

    afiliado = models.ForeignKey(PerfilAfiliado, on_delete=models.CASCADE, related_name='withdrawal_requests')
    # Comisiones confirmadas que cubre la solicitud, ya descontado lo que se
    # recupera (`recovery_amount`). Antes de gastos de transaccion.
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # Comisiones ya pagadas de pedidos que luego se devolvieron o reembolsaron:
    # se descuentan de este pago en lugar de perderse.
    recovery_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Gastos de transaccion a cargo del afiliado; los registra quien paga.
    transaction_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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
        return f"Retiro {self.afiliado.user.email}: ${self.amount}"

    @property
    def net_paid(self):
        """Lo que efectivamente recibe el afiliado."""
        return self.amount - self.transaction_fee


class CommissionStatus(models.TextChoices):
    PENDING = 'pending', 'Pendiente'
    # Se conserva el valor `approved` en la base de datos; para el afiliado
    # es una comision "confirmada": termino su periodo de validacion.
    APPROVED = 'approved', 'Confirmada'
    PAID = 'paid', 'Pagada'
    REVERTED = 'reverted', 'Revertida'
    # Ya se pago y el pedido se devolvio o reembolso despues: se descuenta
    # del siguiente pago.
    CLAWBACK = 'clawback', 'Por recuperar'


class Commission(models.Model):
    """Comision de un pedido referido, con el ciclo de vida documentado en
    el benchmarking (P10): pendiente al aprobarse el pago, confirmada cuando
    termina su periodo de validacion (5 dias habiles despues de la entrega),
    revertida si el pedido se cancela, se devuelve o se reembolsa, y pagada
    cuando se liquida una solicitud de retiro que la incluye."""

    afiliado = models.ForeignKey(PerfilAfiliado, on_delete=models.CASCADE, related_name='commissions')
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='commission')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # Con que base y tasa se calculo `amount`: la tasa del afiliado cambia con
    # el tiempo, y la comision ya registrada debe poder explicarse.
    base_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rate_applied = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=12, choices=CommissionStatus.choices, default=CommissionStatus.PENDING)
    # Una comision marcada para revision no se confirma sola: alguien del
    # equipo decide (p. ej. la compra se parece a una autocompra).
    needs_review = models.BooleanField(default=False)
    review_reason = models.CharField(max_length=255, blank=True)
    # Fin del periodo de validacion: se fija al entregarse el pedido. Si el
    # equipo lo extiende, `extended_until` manda mientras sea posterior.
    validation_ends_at = models.DateTimeField(null=True, blank=True)
    extended_until = models.DateTimeField(null=True, blank=True)
    extension_reason = models.CharField(max_length=255, blank=True)
    # Anulacion o ajuste manual del equipo.
    adjustment_reason = models.CharField(max_length=255, blank=True)
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    adjusted_at = models.DateTimeField(null=True, blank=True)
    withdrawal_request = models.ForeignKey(
        WithdrawalRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='commissions',
    )
    # Solicitud en la que se descuenta esta comision, cuando ya se pago y el
    # pedido se devolvio o reembolso despues (estado "por recuperar"). Es
    # distinta de `withdrawal_request`, que conserva la solicitud en la que se
    # pago.
    recovered_in = models.ForeignKey(
        WithdrawalRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='recovered_commissions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comision {self.order.order_number}: ${self.amount} ({self.status})"

    @property
    def confirmation_date(self):
        """Cuando termina la validacion: la fecha de extension si es mas
        tarde que la original. None mientras el pedido no se haya entregado."""
        if self.validation_ends_at is None:
            return None
        if self.extended_until and self.extended_until > self.validation_ends_at:
            return self.extended_until
        return self.validation_ends_at

    @property
    def validation_last_day(self):
        """Ultimo dia en que la comision sigue en validacion (se confirma al
        dia siguiente). None mientras el pedido no se haya entregado."""
        fin = self.confirmation_date
        if fin is None:
            return None
        return (timezone.localtime(fin) - timedelta(days=1)).date()


class ReferralClick(models.Model):
    """Un uso del enlace de referido (`?ref=<codigo>`) de un afiliado.

    Se registra una sola vez por sesion y por codigo (ver
    `afiliados.middleware.ReferralTrackingMiddleware`), para que recargar
    la pagina no infle el conteo. Junto con `total_referred` permite una
    metrica basica de conversion (ventas / clics) sin necesitar un sistema
    de analitica propio."""

    afiliado = models.ForeignKey(PerfilAfiliado, on_delete=models.CASCADE, related_name='referral_clicks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Clic de {self.afiliado.referral_code} ({self.created_at:%Y-%m-%d %H:%M})"


def almacen_de_recursos():
    """Los recursos de marca son solo para afiliados: no se guardan bajo
    `MEDIA_ROOT`, que se sirve a cualquiera que conozca la ruta."""
    return FileSystemStorage(location=settings.RECURSOS_AFILIADOS_ROOT)


class RecursoMarca(models.Model):
    """Material de apoyo para afiliados (logos, imagenes, lanzamientos) que
    el equipo sube desde el panel de administracion. Se descarga por una
    vista que exige ser afiliado aprobado."""

    title = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    file = models.FileField(upload_to='recursos/', storage=almacen_de_recursos)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Recurso de marca"
        verbose_name_plural = "Recursos de marca"

    def __str__(self):
        return self.title

    @property
    def extension(self):
        nombre = self.file.name or ''
        return nombre.rsplit('.', 1)[-1].upper() if '.' in nombre else ''
