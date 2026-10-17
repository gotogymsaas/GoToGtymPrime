from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path
from gotogym.ratelimit import rate_limit

from . import views

# El correo de recuperacion sale en espanol y con el enlace al sitio publico
# (`SITIO_URL`), no con el dominio que traiga la peticion.
# Cada envio manda un correo: 5 solicitudes cada 10 minutos por IP.
recuperar_contrasena = rate_limit('password_reset', limit=5, period_seconds=600, metodos=('POST',))(
    auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset_form.html',
        email_template_name='accounts/password_reset_email.txt',
        html_email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        extra_email_context={'sitio_url': settings.SITIO_URL},
    )
)

urlpatterns = [
    path('acceso/', views.commercial_login_view, name='commercial_login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('password_reset/', recuperar_contrasena, name='password_reset_form'),
    path('password_reset/', recuperar_contrasena, name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),
    path('editar-perfil/', views.edit_profile, name='edit_profile'),
    path('direcciones/', views.address_book, name='address_book'),
    path('direcciones/nueva/', views.address_edit, name='address_new'),
    path('direcciones/<int:pk>/editar/', views.address_edit, name='address_edit'),
    path('direcciones/<int:pk>/eliminar/', views.address_delete, name='address_delete'),
    path('direcciones/<int:pk>/predeterminada/', views.address_set_default, name='address_set_default'),
]
