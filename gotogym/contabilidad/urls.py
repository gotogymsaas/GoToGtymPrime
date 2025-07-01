from django.urls import path
from . import views

app_name = 'contabilidad'

urlpatterns = [
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/<int:cliente_id>/facturas/', views.facturas_cliente, name='facturas_cliente'),
]
