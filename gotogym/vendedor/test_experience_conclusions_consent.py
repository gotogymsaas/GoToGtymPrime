"""CCB commercial conclusions: strict opt-in, migration and safe revocation."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from gotogym_oidc.models import ExternalIdentityLink

from .consentimiento import aplicar
from .identidad import emitir, verificar
from .models import CommerceConsentAuditEvent, CommercePersonalizationConsent
from .personalizacion import SCOPES_VISIBLES, contexto

SCOPE = "experiences.commerce_conclusions"


class ExperienceConclusionsPermissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="consented-textile", email="textile@example.invalid", password="test-only-secret"
        )
        self.client.force_login(self.user)

    def test_new_permission_starts_off_even_with_experience_completion_optin(self):
        row = aplicar(self.user, "experiences.commerce_guidance", True)
        self.assertFalse(row.is_active(SCOPE))
        self.assertFalse(row.experience_conclusions)
        self.assertIn(SCOPE, {scope for scope, _, _ in SCOPES_VISIBLES})

    def test_specific_consent_is_audited_and_revocable(self):
        row = aplicar(self.user, SCOPE, True)
        self.assertTrue(row.is_active(SCOPE))
        self.assertIn(SCOPE, row.granted_at)
        row = aplicar(self.user, SCOPE, False)
        self.assertFalse(row.is_active(SCOPE))
        self.assertEqual(
            list(CommerceConsentAuditEvent.objects.filter(user=self.user, scope=SCOPE)
                 .values_list("allowed", flat=True)), [True, False],
        )

    def test_bulk_enable_does_not_enable_independent_conclusions(self):
        with patch("vendedor.personalizacion._vinculado", return_value=True):
            response = self.client.post(reverse("vendedor:personalizacion_todo"), {"accion": "activar"})
        self.assertEqual(response.status_code, 302)
        row = CommercePersonalizationConsent.objects.get(user=self.user)
        self.assertFalse(row.is_active(SCOPE))
        self.assertTrue(row.is_active("experiences.commerce_guidance"))
        self.assertTrue(contexto(self.user)["todo_activo"])

    def test_explicit_form_optin_then_bulk_disable_revokes(self):
        with patch("vendedor.personalizacion._vinculado", return_value=True):
            response = self.client.post(reverse("vendedor:personalizacion_permisos"), {"scopes": [SCOPE]})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CommercePersonalizationConsent.objects.get(user=self.user).is_active(SCOPE))
        self.client.post(reverse("vendedor:personalizacion_todo"), {"accion": "desactivar"})
        self.assertFalse(CommercePersonalizationConsent.objects.get(user=self.user).is_active(SCOPE))

    def test_unrelated_account_never_inherits_permission(self):
        other = get_user_model().objects.create_user(
            username="other-textile", email="other-textile@example.invalid", password="test-only-secret"
        )
        aplicar(self.user, SCOPE, True)
        self.assertFalse(CommercePersonalizationConsent.objects.filter(user=other).exists())
        self.assertFalse(CommerceConsentAuditEvent.objects.filter(user=other).exists())


    @override_settings(
        GOTOGYM_OIDC={"ISSUER": "https://verified.example/tenant/v2.0"},
        VENDEDOR_IDENTIDAD_CLAVE_ID="test-key",
        VENDEDOR_IDENTIDAD_SECRETO="test-only-secret-not-for-production",
    )
    def test_signed_assertion_contains_only_live_exact_scopes(self):
        ExternalIdentityLink.objects.create(
            user=self.user, issuer="https://verified.example/tenant/v2.0", subject="verified-oid",
        )
        aplicar(self.user, "experiences.commerce_guidance", True)
        packet = emitir(self.user)
        self.assertIsNotNone(packet)
        decoded = verificar("test-only-secret-not-for-production", packet)
        self.assertNotIn(SCOPE, decoded["scopes"])
        aplicar(self.user, SCOPE, True)
        packet = emitir(self.user)
        decoded = verificar("test-only-secret-not-for-production", packet)
        self.assertIn(SCOPE, decoded["scopes"])
        aplicar(self.user, SCOPE, False)
        self.assertNotIn(SCOPE, verificar("test-only-secret-not-for-production", emitir(self.user))["scopes"])
