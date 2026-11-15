"""New opt-in does not change permissions of existing Shop customers."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .consentimiento import aplicar
from .models import CommerceConsentAuditEvent, CommercePersonalizationConsent, SCOPE_FIELDS
from .personalizacion import SCOPES_VISIBLES

SCOPE = "experiences.commerce_guidance"


class ExperienceGuidanceConsentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="experience_user", email="experience@test.example", password="not-a-real-secret"
        )

    def test_new_scope_opt_in_default_false_even_for_prior_user(self):
        row = CommercePersonalizationConsent.objects.create(user=self.user)
        self.assertIn(SCOPE, SCOPE_FIELDS)
        self.assertIn(SCOPE, {s for s, _label, _description in SCOPES_VISIBLES})
        self.assertFalse(row.experience_guidance)
        self.assertNotIn(SCOPE, row.active_scopes())

    def test_ask_once_via_explicit_action_and_revoke_immediately(self):
        now = timezone.now()
        row = aplicar(self.user, SCOPE, True, now)
        self.assertTrue(row.is_active(SCOPE, now))
        self.assertTrue(row.granted_at[SCOPE])
        row = aplicar(self.user, SCOPE, False, now)
        self.assertFalse(row.is_active(SCOPE, now))
        self.assertNotIn(SCOPE, row.granted_at)
        self.assertEqual(
            list(CommerceConsentAuditEvent.objects.filter(user=self.user, scope=SCOPE).values_list("allowed", flat=True)),
            [True, False],
        )

    def test_old_profile_scope_does_not_grant_experience_status(self):
        row = aplicar(self.user, "profile.basic", True)
        self.assertTrue(row.is_active("profile.basic"))
        self.assertFalse(row.is_active(SCOPE))

    def test_revocation_without_existing_consent_is_noop(self):
        self.assertIsNone(aplicar(self.user, SCOPE, False))
        self.assertFalse(CommerceConsentAuditEvent.objects.filter(user=self.user).exists())
