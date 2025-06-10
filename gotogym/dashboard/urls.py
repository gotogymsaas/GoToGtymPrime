from django.urls import path
from .views import auth_dashboard

app_name = "dashboard"

urlpatterns = [
    path("", auth_dashboard, name="auth_dashboard"),
]
