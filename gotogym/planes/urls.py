from django.urls import path
from . import views

urlpatterns = [
    path('', views.planes_view, name='planes_list'),
]
