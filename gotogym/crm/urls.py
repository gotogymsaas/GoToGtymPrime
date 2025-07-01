from django.urls import path
from . import views

urlpatterns = [
    # Aquí puedes agregar endpoints para sincronizar o consultar datos de HubSpot
    path('contacts/', views.hubspot_contacts, name='hubspot_contacts'),
]
