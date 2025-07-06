from django.shortcuts import render
from .hubspot_service import HubSpotService

def dashboard(request):
    hubspot = HubSpotService()
    contacts = []
    try:
        response = hubspot.get_contacts()
        contacts = response.results if hasattr(response, 'results') else []
    except Exception as e:
        contacts = []
        error = str(e)
        return render(request, 'crm/dashboard.html', {'contacts': contacts, 'error': error})
    return render(request, 'crm/dashboard.html', {'contacts': contacts})
