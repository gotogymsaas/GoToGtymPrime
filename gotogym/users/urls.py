<<<<<<< HEAD
# from django.urls import path
=======
from django.urls import path
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
from django.contrib.auth.views import LoginView, LogoutView

from users.views import RegisterView, UserProfileUpdateView, UserProfileCreateView


<<<<<<< HEAD


from django.urls import path
from .views import CustomLoginView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
=======
urlpatterns = [
    path("login/", LoginView.as_view(template_name="users/login.html"), name="login"),
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
    path("logout/", LogoutView.as_view(), name="logout"),
    path("registro/", RegisterView.as_view(), name="register"),
    path("actualizar", UserProfileUpdateView.as_view(), name="actualizar"),
    path('crear-usuario/', UserProfileCreateView.as_view(), name='crear_usuario'),
]
