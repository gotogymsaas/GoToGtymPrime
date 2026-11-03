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


class PrimeIdentityAdminPreflightTests(TestCase):
    """The detailed audit never opens its results to unauthenticated customers."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        cache.clear()
        self.addCleanup(cache.clear)
        self.staff = get_user_model().objects.create_user(
            username='oidc-preflight-staff', email='staff@example.test',
            password='Only-Test-Password-123!', is_staff=True,
        )

    def report(self):
        return self.client.get(reverse('prime_identity_admin_preflight'))

    def test_anonymous_cannot_read_identity_diagnostics(self):
        response = self.report()
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])
        self.assertNotIn('checks', response.content.decode())

    def test_customer_cannot_read_identity_diagnostics(self):
        from django.contrib.auth import get_user_model
        customer = get_user_model().objects.create_user(
            username='oidc-preflight-customer', email='customer@example.test',
            password='Only-Test-Password-456!',
        )
        self.client.force_login(customer)
        response = self.report()
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('checks', response.content.decode())

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=False, OIDC_CANARY=False)
    def test_staff_sees_failed_checks_while_login_stays_disabled(self):
        self.client.force_login(self.staff)
        with mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA):
            response = self.report()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['mode'], 'disabled')
        self.assertTrue(data['ready'])
        self.assertTrue(any(x['check'] == 'migraciones_aplicadas' for x in data['checks']))
        self.assertTrue(any(x['check'] == 'client_secret_resuelto' for x in data['checks']))
        self.assertTrue(all('detail' not in x for x in data['checks']))
        self.assertNotIn(CONFIG['CLIENT_SECRET'], response.content.decode())
        self.assertIn('no-store', response['Cache-Control'])

    @override_settings(
        GOTOGYM_OIDC={**CONFIG, 'CLIENT_SECRET': '@Microsoft.KeyVault(SecretUri=private-sentinel)'},
        OIDC_GLOBAL=False, OIDC_CANARY=False,
    )
    def test_admin_exposes_failure_bool_but_not_unresolved_reference(self):
        self.client.force_login(self.staff)
        with mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA):
            response = self.report()
        self.assertFalse(response.json()['ready'])
        checks = {v['check']: v['ok'] for v in response.json()['checks']}
        self.assertFalse(checks['client_secret_resuelto'])
        self.assertNotIn('private-sentinel', response.content.decode())
        self.assertNotIn('@Microsoft.KeyVault', response.content.decode())

    def test_staff_diagnostics_does_not_modify_existing_accounts(self):
        from django.contrib.auth import get_user_model

        self.client.force_login(self.staff)
        model = get_user_model()
        before = list(model.objects.order_by('pk').values())
        with mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA):
            self.assertEqual(self.report().status_code, 200)
        self.assertEqual(before, list(model.objects.order_by('pk').values()))

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_GLOBAL=False)
    def test_admin_diagnostics_failure_hides_exception_details(self):
        self.client.force_login(self.staff)
        with mock.patch(
            'accounts.identity_status.verificaciones_de_configuracion',
            side_effect=RuntimeError('SENSITIVE_PRIVATE_SETTINGS_SENTINEL'),
        ):
            response = self.report()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['ready'])
        self.assertEqual(response.json()['diagnostic'], 'unavailable')
        self.assertNotIn('SENSITIVE_PRIVATE_SETTINGS_SENTINEL', response.content.decode())

    def test_diagnostics_rejects_post_requests(self):
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.post(reverse('prime_identity_admin_preflight')).status_code, 405
        )
