from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    path("", views.CartDetail.as_view(),           name="detail"),
    path("checkout/", views.CheckoutView.as_view(),    name="checkout"),
    path("add/<int:pk>/",    views.AddToCart.as_view(),    name="add"),
    path("remove/<int:pk>/", views.RemoveFromCart.as_view(), name="remove"),
    path("update/<int:pk>/",  views.UpdateCart.as_view(),     name="update"),
]
