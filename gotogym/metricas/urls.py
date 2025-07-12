from django.urls import path
from . import views

app_name = 'metricas'

urlpatterns = [
    path('', views.dashboard, name='metricas_dashboard'),
]
