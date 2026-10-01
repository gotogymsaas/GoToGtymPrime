from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, username=None, first_name=None, last_name=None, age=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        # first_name/last_name no aceptan NULL en la base (ver DJ001): un
        # caller que no los pase, o los pase explicitamente en None, debe
        # terminar guardando '' y no None.
        user = self.model(
            email=email, username=username,
            first_name=first_name or '', last_name=last_name or '',
            age=age, **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, username=None, first_name=None, last_name=None, age=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')
        return self.create_user(email, password, username, first_name, last_name, age, **extra_fields)

class CustomerSegment(models.Model):
    """Segmento de clientes (p. ej. mayorista, entrenador, club) usado para
    aplicar condiciones diferenciadas de precio o comunicacion. Es
    deliberadamente generico: quien lo usa decide el criterio de precio, no
    el modelo."""

    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    accepted_terms = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_hash = models.CharField(max_length=128, blank=True)
    show_influencer_modal = models.BooleanField(default=True)  # Nuevo campo
    es_influencer = models.BooleanField(default=False, verbose_name="Es influencer")
    customer_segments = models.ManyToManyField(
        CustomerSegment, blank=True, related_name='members', verbose_name="Segmentos de cliente",
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    # django-stubs tipa AbstractUser.objects como
    # django.contrib.auth.models.UserManager[User] especificamente; este
    # UserManager hereda de BaseUserManager (no de esa clase concreta)
    # porque implementa create_user/create_superuser propios basados en
    # email, no en username. El mismatch es solo de tipos -- cambiar la
    # herencia para complacer a mypy tocaria una clase de autenticacion
    # por un aviso sin impacto en runtime, así que se ignora puntual.
    objects = UserManager()  # type: ignore[assignment,misc]

    def __str__(self):
        return self.email


class CustomerAddress(models.Model):
    """Libreta de direcciones del cliente, reutilizable entre pedidos.

    Independiente de `orders.Address` (que congela la direccion de un
    pedido puntual): esta vive en la cuenta y se puede editar o borrar sin
    afectar pedidos ya hechos."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=60, blank=True, help_text="Ej. Casa, Oficina")
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=40)
    country = models.CharField(max_length=80, default='Colombia')
    department = models.CharField(max_length=80)
    city = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=20, blank=True)
    address_line = models.CharField(max_length=255)
    address_complement = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.label or self.full_name} - {self.city}"
