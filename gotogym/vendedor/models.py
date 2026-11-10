"""Opt-in granular para uso de contexto del Coach en compras.

No habilita ninguna lectura de perfil ni modifica el contrato COMMERCE v1.
"""
from django.conf import settings
from django.db import models


class CommercePersonalizationConsent(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="commerce_personalization_consent",
    )
    profile_basic = models.BooleanField(default=False)
    sports_preferences = models.BooleanField(default=False)
    experiences_summary = models.BooleanField(default=False)
    tailoring_measurements = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Commerce consent for user {self.user_id} (v{self.version})"


class CommerceConsentAuditEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="commerce_consent_audit",
    )
    scope = models.CharField(max_length=64)
    allowed = models.BooleanField()
    consent_version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Commerce consent event {self.pk} for user {self.user_id}"
