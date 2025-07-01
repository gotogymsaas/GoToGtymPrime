# Aquí se agregarán las vistas para la integración con HubSpot CRM
from django.shortcuts import render
from django.http import JsonResponse
import requests
from .hubspot_config import HUBSPOT_API_KEY

def home(request):
    return render(request, 'crm/home.html')

def hubspot_contacts(request):
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {
        "limit": 10,
        "properties": "firstname,lastname,email,phone"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        contacts = data.get('results', [])
    else:
        contacts = []
    return render(request, 'crm/contacts.html', {"contacts": contacts, "status": response.status_code})
