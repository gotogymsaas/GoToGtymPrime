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

class User(AbstractUser):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    accepted_terms = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_hash = models.CharField(max_length=128, blank=True)
    show_influencer_modal = models.BooleanField(default=True)  # Nuevo campo
    es_influencer = models.BooleanField(default=False, verbose_name="Es influencer")

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
