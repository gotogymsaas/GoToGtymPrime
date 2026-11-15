"""Publicación legal CCB 2026-11-14: versión aprobada y opt-in comercial separado."""
import hashlib
from pathlib import Path

from accounts.views import TERMS_PATH
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from vendedor.models import CommercePersonalizationConsent

EN = Path(__file__).resolve().parent / "templates" / "accounts" / "terms_and_conditions_en.html"


class TermsCCBReleaseTests(TestCase):
    def test_both_languages_show_the_same_version_and_commercial_limits(self):
        es = TERMS_PATH.read_text(encoding="utf-8")
        en = EN.read_text(encoding="utf-8")
        self.assertIn("14 de noviembre de 2026", es)
        self.assertIn("14 November 2026", en)
        for doc in (es, en):
            self.assertIn("2026-11-14", doc)
            self.assertNotIn("pending approval", doc)
            self.assertNotIn("pendiente de aprobación", doc)
            self.assertIn("privacy@gotogym.store", doc)

    def test_new_shop_acceptance_is_hash_of_current_text_not_automatic_commerce_opt_in(self):
        credentials = {
            "first_name": "Luis", "last_name": "Soto", "age": "28",
            "email": "ccb-terms@example.com", "password1": "Clave-Segura-123",
            "password2": "Clave-Segura-123", "accepted_terms": "on",
        }
        self.client.post(reverse("register"), credentials)
        user = get_user_model().objects.get(email=credentials["email"])
        expected = hashlib.sha512(TERMS_PATH.read_bytes()).hexdigest()
        self.assertEqual(user.terms_hash, expected)
        self.assertTrue(user.accepted_terms)
        self.assertFalse(CommercePersonalizationConsent.objects.filter(user=user).exists())

    def test_active_registration_displays_approved_terms(self):
        response = self.client.get(reverse("register"))
        self.assertContains(response, "Continuidad comercial de conclusiones útiles")
        self.assertContains(response, "2026-11-14")
