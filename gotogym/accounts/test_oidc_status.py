"""Security and rollout checks for the public Prime OIDC status endpoint."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.test_oidc import CONFIG, METADATA


class PrimeIdentityStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def status(self):
        return self.client.get(reverse('prime_identity_status'))

    def test_disabled_remains_disabled_even_without_provider(self):
        response = self.status()
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()['enabled'], False)
        self.assertIs(response.json()['canary'], False)
        self.assertEqual(response['Cache-Control'].split(',')[0], 'max-age=0')

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=True, OIDC_CANARY=False)
    def test_global_mode_only_enabled_when_ready(self):
        with mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA):
            response = self.status()
        self.assertEqual(response.json(), {'enabled': True, 'canary': False, 'ready': True})

    @override_settings(
        GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=False, OIDC_CANARY=True,
        OIDC_CANARY_OBJECT_IDS=frozenset({'canary-test-oid'}),
    )
    def test_canary_is_not_reported_as_global_access(self):
        with mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA):
            response = self.status()
        self.assertEqual(response.json(), {'enabled': False, 'canary': True, 'ready': True})

    @override_settings(
        GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=False, OIDC_CANARY=True,
        OIDC_CANARY_OBJECT_IDS=frozenset(),
    )
    def test_empty_canary_list_is_not_ready(self):
        with mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA):
            self.assertEqual(self.status().json(), {'enabled': False, 'canary': False, 'ready': False})

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=True)
    def test_provider_issuer_mismatch_fails_closed(self):
        with mock.patch('gotogym_oidc.client.get_metadata', return_value={**METADATA, 'issuer': 'https://wrong.example/'}):
            self.assertEqual(self.status().json(), {'enabled': False, 'canary': False, 'ready': False})

    @override_settings(GOTOGYM_OIDC={**CONFIG, 'CLIENT_SECRET': '@Microsoft.KeyVault(secret-placeholder)'}, OIDC_GLOBAL=True)
    def test_unresolved_key_vault_reference_fails_closed(self):
        with mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA):
            response = self.status()
        self.assertEqual(response.json(), {'enabled': False, 'canary': False, 'ready': False})
        self.assertNotIn('KeyVault', response.content.decode())
        self.assertNotIn('secret-placeholder', response.content.decode())

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=True)
    def test_does_not_report_ready_on_db_error(self):
        with mock.patch('accounts.identity_status.verificaciones_de_configuracion', side_effect=RuntimeError('private-database-error')):
            response = self.status()
        self.assertIs(response.json()['ready'], False)
        self.assertNotIn('private-database-error', response.content.decode())

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=True)
    def test_post_is_rejected(self):
        self.assertEqual(self.client.post(reverse('prime_identity_status')).status_code, 405)

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=True)
    def test_status_does_not_modify_local_users(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(email='preserved@example.com', username='preserved', password='Test-Only-456!')
        before = list(get_user_model().objects.values())
        with mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA):
            self.status()
        self.assertEqual(before, list(get_user_model().objects.values()))
        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())
