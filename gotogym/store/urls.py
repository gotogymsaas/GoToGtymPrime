from django.urls import path
from . import views

app_name = "store"          # ←  Debe ser "store" si en las plantillas llamas ‘store:…’

urlpatterns = [
    path("", views.ProductGrid.as_view(), name="catalog"),
    path("<int:pk>/", views.ProductDetail.as_view(), name="detail"),   # ← pide pk
]

