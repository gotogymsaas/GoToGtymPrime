from django.contrib.auth.models import User
from django.test import TestCase
from unittest.mock import patch


class HubSpotSignalTests(TestCase):
    @patch("integrations.hubspot.hubspot_client.HubSpotClient")
    def test_create_contact_called_on_user_save(self, mock_client_cls):
        """Saving a new user should trigger a HubSpot contact creation."""
        User.objects.create_user("john", "john@example.com", "pwd")

        mock_client_cls.return_value.create_contact.assert_called_once_with(
            "john@example.com", {}
        )

