from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    nit = models.IntegerField(verbose_name="NIT", null=True, blank=True)
    phone = models.IntegerField(verbose_name="Teléfono", null=True, blank=True)
    logo = models.ImageField(
        upload_to="logos/", default="logos/usergenerics.png", verbose_name="Cargar Logo"
    )
    contact_name = models.CharField(
        max_length=100, verbose_name="Nombre de la Persona a Cargo"
    )
    position = models.CharField(max_length=100, verbose_name="Cargo", null=True, blank=True)
    empresa = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name= 'perfil'
        verbose_name_plural = 'perfiles'
        ordering = ['-id']

    def __str__(self):
        return self.user.username




