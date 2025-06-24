import os
from django.test import SimpleTestCase
from unittest.mock import patch

from integrations.alegra.alegra_client import AlegraClient


class AlegraClientTests(SimpleTestCase):
    @patch.dict(os.environ, {"ALEGRA_EMAIL": "user@example.com", "ALEGRA_TOKEN": "token"})
    def test_initializes_from_env(self):
        client = AlegraClient()
        self.assertEqual(client.email, "user@example.com")
        self.assertEqual(client.token, "token")
