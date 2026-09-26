from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/cotizar-envio/', views.cotizar_envio, name='cotizar_envio'),
    path('mis-pedidos/', views.my_orders, name='my_orders'),
    path('pedido/<str:order_number>/', views.order_detail, name='order_detail'),
    path('pedido/<str:order_number>/item/<int:item_id>/review/', views.create_review, name='create_review'),
]
