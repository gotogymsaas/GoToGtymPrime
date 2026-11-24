from django.test import SimpleTestCase, override_settings

from integrations.alegra.alegra_client import AlegraClient


class AlegraClientTests(SimpleTestCase):
    @override_settings(ALEGRA_EMAIL="user@example.com", ALEGRA_API_TOKEN="token")
    def test_initializes_from_env(self):
        client = AlegraClient()
        self.assertEqual(client.email, "user@example.com")
        self.assertEqual(client.token, "token")
