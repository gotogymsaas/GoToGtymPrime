"""Regresiones del consentimiento omnicanal: nunca se comparten datos por defecto."""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from gotogym_oidc.models import ExternalIdentityLink

from .models import CommerceConsentAuditEvent, CommercePersonalizationConsent

URL = "/es/vendedor/consentimiento/"


class CommerceConsentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="comprador", email="comprador@example.com", password="test-only-password",
        )
        self.other = get_user_model().objects.create_user(
            username="otro", email="otro@example.com", password="test-only-password",
        )
        self.client.force_login(self.user)

    def link(self, user=None):
        return ExternalIdentityLink.objects.create(
            user=user or self.user, issuer="https://verified.example/tenant/v2.0",
            subject="oid-" + str((user or self.user).pk),
        )

    def post(self, scope, allowed, client=None):
        return (client or self.client).post(
            URL, data=json.dumps({"scope": scope, "allowed": allowed}),
            content_type="application/json",
        )

    def test_unlinked_account_cannot_enable_personalization(self):
        self.assertEqual(self.post("profile.basic", True).status_code, 403)
        self.assertFalse(CommercePersonalizationConsent.objects.exists())

    def test_existing_link_is_not_automatic_consent(self):
        self.link()
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["linked"])
        self.assertFalse(any(response.json()["scopes"].values()))
        self.assertEqual(CommerceConsentAuditEvent.objects.count(), 0)

    def test_grant_and_revoke_are_versioned_audited(self):
        self.link()
        granted = self.post("tailoring.measurements", True).json()
        self.assertTrue(granted["scopes"]["tailoring.measurements"])
        self.assertFalse(granted["scopes"]["profile.basic"])
        self.assertEqual(granted["version"], 2)
        revoked = self.post("tailoring.measurements", False).json()
        self.assertFalse(revoked["scopes"]["tailoring.measurements"])
        self.assertEqual(revoked["version"], 3)
        self.assertEqual(
            list(CommerceConsentAuditEvent.objects.order_by("pk").values_list("allowed", flat=True)),
            [True, False],
        )
        self.assertEqual(CommercePersonalizationConsent.objects.count(), 1)

    def test_cannot_read_or_change_other_users_consent(self):
        self.link()
        self.link(self.other)
        self.post("profile.basic", True)
        other_client = Client()
        other_client.force_login(self.other)
        own = other_client.get(URL).json()
        self.assertFalse(own["scopes"]["profile.basic"])
        self.assertEqual(CommercePersonalizationConsent.objects.count(), 1)

    def test_idempotent_grant_does_not_duplicate_audit(self):
        self.link()
        first = self.post("profile.basic", True).json()
        second = self.post("profile.basic", True).json()
        self.assertEqual(first["version"], second["version"])
        self.assertEqual(CommerceConsentAuditEvent.objects.count(), 1)

    def test_reject_unknown_scope_and_non_boolean(self):
        self.link()
        self.assertEqual(self.post("clinical.history", True).status_code, 400)
        self.assertEqual(self.post("profile.basic", "true").status_code, 400)
        self.assertFalse(CommercePersonalizationConsent.objects.exists())

    def test_post_requires_csrf_in_browser(self):
        self.link()
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(
            browser.post(URL, data=json.dumps({"scope": "profile.basic", "allowed": True}),
                         content_type="application/json").status_code, 403,
        )
        self.assertFalse(CommercePersonalizationConsent.objects.exists())


class CommerceConsentLifecycleTests(TestCase):
    """Revocacion sin enlace, caducidad de 12 meses y memoria comercial."""

    setUp = CommerceConsentTests.setUp
    link = CommerceConsentTests.link
    post = CommerceConsentTests.post

    def test_revoke_works_after_unlinking(self):
        link = self.link()
        self.post("profile.basic", True)
        link.delete()
        response = self.post("profile.basic", False)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["scopes"]["profile.basic"])
        self.assertFalse(CommercePersonalizationConsent.objects.get().profile_basic)

    def test_grant_still_requires_link(self):
        self.assertEqual(self.post("conversation.commerce_memory", True).status_code, 403)

    def test_commerce_memory_scope_is_opt_in(self):
        self.link()
        self.assertFalse(self.client.get(URL).json()["scopes"]["conversation.commerce_memory"])
        granted = self.post("conversation.commerce_memory", True).json()
        self.assertTrue(granted["scopes"]["conversation.commerce_memory"])
        self.assertIn("conversation.commerce_memory", granted["expires_at"])

    def test_grant_expires_after_twelve_months_and_can_be_renewed(self):
        self.link()
        self.post("sports.preferences", True)
        row = CommercePersonalizationConsent.objects.get()
        row.granted_at = {"sports.preferences": (timezone.now() - timedelta(days=366)).isoformat()}
        row.save()
        self.assertFalse(self.client.get(URL).json()["scopes"]["sports.preferences"])
        renewed = self.post("sports.preferences", True).json()
        self.assertTrue(renewed["scopes"]["sports.preferences"])
        self.assertEqual(CommerceConsentAuditEvent.objects.filter(allowed=True).count(), 2)

    def test_grant_without_date_is_never_active(self):
        self.link()
        CommercePersonalizationConsent.objects.create(user=self.user, profile_basic=True)
        self.assertFalse(self.client.get(URL).json()["scopes"]["profile.basic"])
