from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('pedido/<str:order_number>/', views.payment_pending, name='pending'),
    path('pedido/<str:order_number>/simular/<str:status>/', views.simulate, name='simulate'),
    # El webhook NO va aqui: esta app se incluye dentro de i18n_patterns, y un
    # webhook real no antepone un prefijo de idioma. Se registra en
    # gotogym/urls.py, fuera del bloque i18n_patterns.
]
