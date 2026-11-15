"""Pruebas unitarias del motor SGAE; Python standard library, sin DB."""
from datetime import datetime, timedelta, timezone
import unittest

from qaf_legal_decision_engine import Action, ConsentProof, general_service_after_decline, resolve


NOW = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)


def evaluate(proof=None, **kwargs):
    opts = dict(
        identity_verified=True,
        required_contract_version="shop-2026-11",
        accepted_contract_version="shop-2026-11",
        optional_purpose="commerce.profile",
        product="shop",
        notice_version="notice-v1",
        proof=proof,
        now=NOW,
    )
    opts.update(kwargs)
    return resolve(**opts)


def permitted(**overrides):
    fields = dict(purpose="commerce.profile", product="shop", allowed=True,
                  notice_version="notice-v1", captured_at=NOW - timedelta(days=1),
                  expires_at=NOW + timedelta(days=90))
    fields.update(overrides)
    return ConsentProof(**fields)


class DecisionTests(unittest.TestCase):
    def test_no_link_never_reads_profile(self):
        x = evaluate(permitted(), identity_verified=False)
        self.assertEqual(x.action, Action.LINK_REQUIRED)
        self.assertFalse(x.personal_context_permitted)

    def test_contract_not_accepted(self):
        x = evaluate(permitted(), accepted_contract_version="old")
        self.assertEqual(x.action, Action.CONTRACT_REQUIRED)

    def test_no_consent_requires_contextual_decision(self):
        x = evaluate()
        self.assertEqual(x.action, Action.OPTIONAL_PERMISSION_REQUIRED)

    def test_exact_valid_proof(self):
        x = evaluate(permitted())
        self.assertEqual(x.action, Action.READY)
        self.assertTrue(x.personal_context_permitted)

    def test_different_purpose_and_product_denied(self):
        self.assertFalse(evaluate(permitted(purpose="marketing.whatsapp")).personal_context_permitted)
        self.assertFalse(evaluate(permitted(product="business")).personal_context_permitted)

    def test_different_notice_version_denied(self):
        self.assertFalse(evaluate(permitted(notice_version="notice-old")).personal_context_permitted)

    def test_revoked(self):
        self.assertFalse(evaluate(permitted(revoked_at=NOW)).personal_context_permitted)

    def test_expired(self):
        self.assertFalse(evaluate(permitted(expires_at=NOW)).personal_context_permitted)

    def test_future_and_naive_proofs(self):
        self.assertFalse(evaluate(permitted(captured_at=NOW + timedelta(days=1))).personal_context_permitted)
        self.assertFalse(evaluate(permitted(captured_at=datetime(2026, 11, 14))).personal_context_permitted)

    def test_optional_rejection_never_blocks_purchase(self):
        x = general_service_after_decline()
        self.assertEqual(x.action, Action.GENERAL_SERVICE)
        self.assertFalse(x.checkout_blocked_by_optional_consent)
        self.assertFalse(x.personal_context_permitted)


if __name__ == "__main__":
    unittest.main()
