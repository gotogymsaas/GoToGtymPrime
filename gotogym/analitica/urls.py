from django.urls import path

from . import views

app_name = 'analitica'

urlpatterns = [
    path('eventos/', views.registrar_eventos, name='registrar_eventos'),
]
