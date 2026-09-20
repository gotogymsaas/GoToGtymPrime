from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('mis-pedidos/', views.my_orders, name='my_orders'),
    path('pedido/<str:order_number>/', views.order_detail, name='order_detail'),
]
