from django.urls import path
from . import views
from . import views_checkout

app_name = 'carrito'

urlpatterns = [
    path('', views.cart_detail, name='cart_detail'),
    path('add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update/<int:product_id>/', views.update_cart, name='update_cart'),
    path('checkout/', views_checkout.checkout, name='checkout'),
    path('payment-status/', views_checkout.payment_status, name='payment_status'),
]
