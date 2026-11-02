from django.conf import settings
from django.db import models


class ExternalIdentityLink(models.Model):
    """Une una cuenta local con la identidad que el IdP central emitio.

    La clave es (issuer, subject), nunca el correo: el correo puede cambiar y
    no prueba que dos personas sean la misma.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='external_identity_links',
    )
    issuer = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    email_at_link = models.EmailField(blank=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['issuer', 'subject'], name='gotogym_oidc_unique_identity'),
            # Una cuenta local solo puede tener una identidad por emisor.
            models.UniqueConstraint(fields=['user', 'issuer'], name='gotogym_oidc_one_identity_per_user'),
        ]

    def __str__(self):
        return f'{self.user_id} <-> {self.issuer}#{self.subject}'


class AuthorizationFlow(models.Model):
    """Only the hash is persisted; DB deletion is the cross-worker one-use gate."""
    digest = models.CharField(max_length=64, primary_key=True)
    expires_at = models.DateTimeField(db_index=True)

    def __str__(self):
        return self.digest
