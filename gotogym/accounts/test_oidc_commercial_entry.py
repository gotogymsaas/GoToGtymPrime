"""Commercial login must not offer a non-operational SSO path."""
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.test_oidc import CONFIG


class ShopIdentityEntryTests(TestCase):
    @override_settings(OIDC_HABILITADO=False, OIDC_GLOBAL=False, OIDC_CANARY=False)
    def test_canary_request_when_disabled_keeps_shop_login(self):
        response = self.client.get(reverse('commercial_login') + '?sso=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acceso GoToGym en preparación para esta tienda.')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, 'Continuar con GoToGym')

    @override_settings(OIDC_HABILITADO=False, OIDC_GLOBAL=False, OIDC_CANARY=False)
    def test_normal_login_does_not_show_internal_canary_notice(self):
        response = self.client.get(reverse('commercial_login'))
        self.assertNotContains(response, 'Acceso GoToGym en preparación para esta tienda.')

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_HABILITADO=True,
                       OIDC_GLOBAL=True, OIDC_CANARY=False, OIDC_SOLO_GOTOGYM=False)
    def test_global_sso_precedes_legacy_form_and_preserves_fallback(self):
        response = self.client.get(reverse('commercial_login'))
        body = response.content.decode()
        self.assertLess(body.index('Continuar con GoToGym'), body.index('id="commercial-auth-form"'))
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'contraseña habitual de la tienda')

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_HABILITADO=True,
                       OIDC_GLOBAL=True, OIDC_CANARY=False, OIDC_SOLO_GOTOGYM=False)
    def test_checkout_return_destination_is_kept(self):
        response = self.client.get(reverse('commercial_login'), {'next': '/orders/checkout/'})
        self.assertContains(response, 'next=%2Forders%2Fcheckout%2F')
        self.assertContains(response, 'name="next"')
