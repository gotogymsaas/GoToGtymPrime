from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from integrations.hubspot.hubspot_client import HubSpotClient
from .models import UserProfile

@receiver(post_save, sender=User)
def create_hubspot_contact(sender, instance, created, **kwargs):
    """Create a HubSpot contact after a new user is saved."""
    if not created:
        return

    try:
        profile = instance.profile
    except UserProfile.DoesNotExist:
        profile = None

    profile_data = {}
    if profile:
        profile_data = {
            "contact_name": profile.contact_name,
            "nit": profile.nit,
            "phone": profile.phone,
            "position": profile.position,
            "empresa": profile.empresa,
        }

    client = HubSpotClient()
    client.create_contact(instance.email, profile_data)
