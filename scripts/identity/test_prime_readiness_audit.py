"""Tests without external network, production access or Azure credentials."""
import contextlib
import importlib.util
import io
import json
import pathlib
import unittest
from unittest import mock

FILE = pathlib.Path(__file__).with_name("prime_readiness_audit.py")
spec = importlib.util.spec_from_file_location("prime_readiness_audit", FILE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def appsettings(client="prime-independent-client", redirect=audit.CALLBACK):
    return [
        {"name": "OIDC_CLIENT_ID", "value": client},
        {"name": "OIDC_ISSUER", "value": audit.ISSUER},
        {"name": "OIDC_DISCOVERY_URL", "value": audit.DISCOVERY},
        {"name": "OIDC_REDIRECT_URI", "value": redirect},
        {"name": "OIDC_POST_LOGOUT_REDIRECT_URI", "value": "https://shop.gotogym.store/"},
        {"name": "OIDC_SUBJECT_CLAIM", "value": "oid"},
        {"name": "OIDC_CLIENT_SECRET", "value": "@Microsoft.KeyVault(SecretUri=https://vault.vault.azure.net/secrets/prime)"},
        {"name": "UNIVERSAL_IDENTITY_ENABLED", "value": "false"},
    ]


class Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        return self.body[:size]


class AuditTests(unittest.TestCase):
    def test_expected_configuration_does_not_reuse_coach(self):
        report = audit.inspect_settings(appsettings())
        self.assertEqual(report["state"], "verified")
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["rollout"]["global"])
        self.assertFalse(report["rollout"]["canary"])

    def test_coach_client_id_is_rejected(self):
        checks = audit.inspect_settings(appsettings(client=audit.COACH_CLIENT_ID))["checks"]
        self.assertFalse(checks["prime_client_is_not_coach_client"])

    def test_redirect_must_be_exact_and_not_attacker_domain(self):
        for redirect in (
            "https://evil.test/accounts/oidc/callback/",
            "http://shop.gotogym.store/accounts/oidc/callback/",
            "https://shop.gotogym.store/accounts/oidc/callback/?next=x",
        ):
            with self.subTest(redirect=redirect):
                self.assertFalse(audit.inspect_settings(appsettings(redirect=redirect))["checks"]["callback_exact"])

    def test_no_credentials_or_user_data_in_report(self):
        secret = "DO-NOT-PRINT-THIS-CLIENT-SECRET"
        settings = appsettings() + [
            {"name": "DJANGO_SECRET_KEY", "value": secret},
            {"name": "DATABASE_URL", "value": secret},
            {"name": "OIDC_CANARY_OBJECT_IDS", "value": secret},
        ]
        report = json.dumps(audit.inspect_settings(settings))
        self.assertNotIn(secret, report)
        self.assertNotIn("prime-independent-client", report)

    def test_public_json_readiness_is_bool_only(self):
        body = json.dumps({"enabled": False, "canary": True, "ready": True, "sensitive": "DO_NOT_INCLUDE"}).encode()
        result = audit.read_public_status(opener=lambda *_a, **_kw: Response(body))
        self.assertEqual(result, {"state": "verified", "enabled": False, "canary": True, "ready": True})
        self.assertNotIn("DO_NOT_INCLUDE", str(result))

    def test_unexpected_public_response_fails_closed(self):
        for obj in ({"enabled": "true", "ready": True, "canary": False}, [], {"enabled": True}):
            with self.subTest(obj=obj):
                result = audit.read_public_status(opener=lambda *_a, **_kw: Response(json.dumps(obj).encode()))
                self.assertEqual(result["state"], "unverified")

    def test_keyvault_status_requires_resolved(self):
        version = {"value": [{"name": "OIDC_CLIENT_SECRET", "properties": {"status": "Resolved"}}]}
        self.assertEqual(audit._status_of_reference(version), "resolved")
        self.assertEqual(audit._status_of_reference({}), "unverified")
        self.assertEqual(audit._status_of_reference({"value": [{"name": "OIDC_CLIENT_SECRET", "properties": {"status": "AccessToKeyVaultDenied"}}]}), "unresolved")

    @mock.patch.object(audit, "_az")
    def test_azure_rbac_denial_is_unverified_no_exception(self, az):
        az.side_effect = [
            ({"id": audit.SUB}, None),
            ({"name": audit.APP, "state": "Running"}, None),
            (None, "azure_rbac_denied"),
        ]
        self.assertEqual(audit.read_azure(), {"state": "unverified", "reason": "azure_rbac_denied"})

    @mock.patch.object(audit, "_az")
    def test_azure_read_only_success(self, az):
        az.side_effect = [
            ({"id": audit.SUB}, None),
            ({"name": audit.APP, "state": "Running", "identity": {"principalId": "fake-id"}}, None),
            (appsettings(), None),
            ({"value": [{"name": "OIDC_CLIENT_SECRET", "properties": {"status": "Resolved"}}]}, None),
        ]
        report = audit.read_azure()
        self.assertTrue(report["app_running"])
        self.assertTrue(report["managed_identity_present"])
        self.assertEqual(report["keyvault_reference_status"], "resolved")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(len(az.call_args_list), 4)

    @mock.patch.object(audit, "_az")
    def test_wrong_subscription_performs_no_followup_queries(self, az):
        az.return_value = ({"id": "OTHER"}, None)
        self.assertEqual(audit.read_azure()["reason"], "unexpected_subscription")
        az.assert_called_once()


if __name__ == "__main__":
    unittest.main()
