from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView

from users.views import RegisterView, UserProfileUpdateView, UserProfileCreateView


urlpatterns = [
    path("login/", LoginView.as_view(template_name="users/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("registro/", RegisterView.as_view(), name="register"),
    path("actualizar", UserProfileUpdateView.as_view(), name="actualizar"),
    path('crear-usuario/', UserProfileCreateView.as_view(), name='crear_usuario'),
]
