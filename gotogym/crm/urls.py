
# from django.urls import path
# from . import views

# urlpatterns = [
    # Aquí puedes agregar endpoints para sincronizar o consultar datos de HubSpot
#     path('contacts/', views.hubspot_contacts, name='hubspot_contacts'),
# ]

from django.http import HttpResponse
from django.urls import path
def healthz(request):
    return HttpResponse("OK")
urlpatterns = [
    # ...
    path("healthz", healthz),
]
