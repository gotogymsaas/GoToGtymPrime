from django.urls import path
from . import views

app_name = 'web'

urlpatterns = [
    path('config/', views.config_web, name='config'),
]
