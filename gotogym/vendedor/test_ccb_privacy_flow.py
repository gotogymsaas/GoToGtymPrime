"""M11/M12/M14: recibo y revocación comercial bajo identidad de sesión propia."""
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from gotogym_oidc.models import ExternalIdentityLink

from .consentimiento import aplicar
from .models import (
    CommerceConsentAuditEvent, CommerceMemoryItem,
    CommercePersonalizationConsent, TailoringMeasurement,
)
from .estado import estado_usuario
from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore

ISSUER = "https://verified.example/tenant/v2.0"
CONFIG = {
    "GOTOGYM_OIDC": {"ISSUER": ISSUER, "SUBJECT_CLAIM": "oid"},
    "VENDEDOR_CONTRATO_V2": True,
    "VENDEDOR_IDENTIDAD_CLAVE_ID": "test-id",
    "VENDEDOR_IDENTIDAD_SECRETO": "different-test-secret",
}


@override_settings(**CONFIG)
class CommercialPrivacyFlowTests(TestCase):
    def setUp(self):
        model = get_user_model()
        self.a = model.objects.create_user(username="ccb_ana", email="ana@example.invalid", password="test-secret")
        self.b = model.objects.create_user(username="ccb_beto", email="beto@example.invalid", password="test-secret")
        self.client.force_login(self.a)
        ExternalIdentityLink.objects.create(user=self.a, issuer=ISSUER, subject="oid-a")

    def test_receipt_private_and_no_pii_or_raw_measurements(self):
        aplicar(self.a, "profile.basic", True)
        aplicar(self.b, "sports.preferences", True)
        TailoringMeasurement.objects.create(
            user=self.a, chest_cm=Decimal("91.5"), captured_at=timezone.now())
        url = reverse("vendedor:privacy_receipt")
        result = self.client.get(url)
        self.assertEqual(result.status_code, 200)
        payload = result.json()
        self.assertTrue(payload["current"]["scopes"]["profile.basic"])
        self.assertFalse(payload["current"]["scopes"]["sports.preferences"])
        self.assertEqual(payload["decision_count"], 1)
        self.assertTrue(payload["data_categories"]["measurements_recorded"])
        self.assertFalse(payload["legal_equivalence_to_other_products"])
        self.assertIn("no-store", result["Cache-Control"])
        for forbidden in ("ana@example.invalid", "oid-a", "91.5", "beto@example.invalid"):
            self.assertNotIn(forbidden, result.content.decode())

    def test_anonymous_cannot_read_receipt_or_revoke(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("vendedor:privacy_receipt")).status_code, 302)
        self.assertEqual(self.client.post(reverse("vendedor:privacy_revoke_all"),
                                          {"confirm": "REVOCAR_PERSONALIZACION"}).status_code, 302)

    def test_revocation_requires_explicit_confirmation(self):
        aplicar(self.a, "profile.basic", True)
        url = reverse("vendedor:privacy_revoke_all")
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {}).status_code, 400)
        self.assertTrue(CommercePersonalizationConsent.objects.get(user=self.a).is_active("profile.basic"))

    def test_revoke_all_erases_optional_data_not_identity_or_other_accounts(self):
        aplicar(self.a, "profile.basic", True)
        aplicar(self.a, "tailoring.measurements", True)
        aplicar(self.a, "conversation.commerce_memory", True)
        aplicar(self.b, "profile.basic", True)
        TailoringMeasurement.objects.create(
            user=self.a, chest_cm=Decimal("91.5"), captured_at=timezone.now())
        CommerceMemoryItem.objects.create(
            user=self.a, kind="color", value="azul", confirmed_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90))
        result = self.client.post(reverse("vendedor:privacy_revoke_all"),
                                  {"confirm": "REVOCAR_PERSONALIZACION"})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(CommercePersonalizationConsent.objects.get(user=self.a).active_scopes(), [])
        self.assertFalse(TailoringMeasurement.objects.filter(user=self.a).exists())
        self.assertFalse(CommerceMemoryItem.objects.filter(user=self.a).exists())
        self.assertTrue(CommercePersonalizationConsent.objects.get(user=self.b).is_active("profile.basic"))
        self.assertTrue(ExternalIdentityLink.objects.filter(user=self.a, subject="oid-a").exists())
        self.assertEqual(CommerceConsentAuditEvent.objects.filter(user=self.a, allowed=False).count(), 3)

    def test_state_proposes_one_nonblocking_next_step(self):
        request = RequestFactory().get("/es/vendedor/estado/")
        request.user = self.a
        request.session = SessionStore()
        before = estado_usuario(request)
        self.assertEqual(before["mode"], "consent_required")
        self.assertEqual(before["next_step"], "optional_personalization")
        aplicar(self.a, "profile.display_name", True)
        after = estado_usuario(request)
        self.assertEqual(after["mode"], "linked")
        self.assertEqual(after["next_step"], "ready")
        self.assertNotEqual(before["epoch"], after["epoch"])
