from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView


urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
    path("login/", auth_views.LoginView.as_view(template_name="administracion/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin-panel/", include("administracion.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
