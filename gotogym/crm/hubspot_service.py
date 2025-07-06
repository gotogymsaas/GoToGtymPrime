from hubspot import HubSpot
from django.conf import settings

class HubSpotService:
    def __init__(self):
        self.client = HubSpot(access_token=settings.HUBSPOT_ACCESS_TOKEN)

    def get_contacts(self):
        return self.client.crm.contacts.basic_api.get_page()

    def create_contact(self, email, firstname=None, lastname=None):
        properties = {"email": email}
        if firstname:
            properties["firstname"] = firstname
        if lastname:
            properties["lastname"] = lastname
        simple_public_object_input = {"properties": properties}
        return self.client.crm.contacts.basic_api.create(simple_public_object_input)
