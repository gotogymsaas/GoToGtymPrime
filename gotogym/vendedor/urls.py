from django.urls import path

from . import consentimiento, views

app_name = 'vendedor'

urlpatterns = [
    path('mensaje/', views.mensaje, name='mensaje'),
    path('consentimiento/', consentimiento.consentimiento, name='consentimiento'),
]
