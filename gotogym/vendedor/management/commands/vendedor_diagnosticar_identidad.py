"""Diagnóstico de personalización Shop→Coach sin imprimir datos personales ni secretos."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from gotogym_oidc.models import ExternalIdentityLink
from vendedor.models import CommercePersonalizationConsent


class Command(BaseCommand):
    help = "Comprueba las precondiciones de identidad del vendedor para un usuario (sin datos personales)."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(pk=options["user_id"]).first()
        if user is None:
            raise CommandError("Usuario no encontrado")
        issuer = (getattr(settings, "GOTOGYM_OIDC", {}) or {}).get("ISSUER")
        linked = bool(issuer) and ExternalIdentityLink.objects.filter(user=user, issuer=issuer).exists()
        consent = CommercePersonalizationConsent.objects.filter(user=user).first()
        scopes = consent.active_scopes() if consent else []
        from vendedor.identidad import credencial
        checks = {
            "authenticated_account_active": bool(user.is_active),
            "contract_v2_enabled": bool(settings.VENDEDOR_CONTRATO_V2),
            "identity_credentials_ready": credencial() is not None,
            "oidc_issuer_configured": bool(issuer),
            "oidc_link_for_issuer": bool(linked),
            "consent_record_present": consent is not None,
            "active_scope_count": len(scopes),
            "identity_ready": bool(user.is_active and settings.VENDEDOR_CONTRATO_V2 and credencial() and linked and scopes),
        }
        for key, value in checks.items():
            self.stdout.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
        if not checks["identity_ready"]:
            self.stdout.write(self.style.WARNING("Personalización no lista; revisar los checks falsos. No se ha modificado ningún dato."))
