from django.urls import path
from . import views

app_name = 'tienda'

urlpatterns = [
    path('', views.producto_list, name='producto_list'),
    path('producto/<int:pk>/', views.producto_detail, name='producto_detail'),
]
