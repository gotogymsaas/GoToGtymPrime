"""Opt-in granular para uso de contexto del Coach en compras.

No habilita ninguna lectura de perfil ni modifica el contrato COMMERCE v1.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Un permiso concedido deja de valer al cumplir este plazo y hay que volver a
# pedirlo. Se cuenta desde la ultima concesion de cada scope.
CONSENT_VALIDITY = timedelta(days=365)

SCOPE_FIELDS = {
    "profile.basic": "profile_basic",
    "sports.preferences": "sports_preferences",
    "experiences.summary": "experiences_summary",
    "tailoring.measurements": "tailoring_measurements",
    "conversation.commerce_memory": "commerce_memory",
}


class CommercePersonalizationConsent(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="commerce_personalization_consent",
    )
    profile_basic = models.BooleanField(default=False)
    sports_preferences = models.BooleanField(default=False)
    experiences_summary = models.BooleanField(default=False)
    tailoring_measurements = models.BooleanField(default=False)
    commerce_memory = models.BooleanField(default=False)
    # Fecha de la ultima concesion por scope ({"profile.basic": iso8601}).
    granted_at = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Commerce consent for user {self.user_id} (v{self.version})"

    def is_active(self, scope, now=None):
        """True solo si el scope esta concedido y la concesion no ha caducado."""
        field = SCOPE_FIELDS[scope]
        if not getattr(self, field):
            return False
        raw = (self.granted_at or {}).get(scope)
        if not raw:
            return False
        try:
            granted = timezone.datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            return False
        return (now or timezone.now()) < granted + CONSENT_VALIDITY

    def active_scopes(self, now=None):
        now = now or timezone.now()
        return sorted(scope for scope in SCOPE_FIELDS if self.is_active(scope, now))


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
