from django.urls import path

from . import views

app_name = 'vendedor'

urlpatterns = [
    path('mensaje/', views.mensaje, name='mensaje'),
]
