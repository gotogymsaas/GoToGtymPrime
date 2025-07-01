from django.contrib.auth import logout
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

# Vista personalizada para logout por GET
def logout_view(request):
    logout(request)
    return redirect('/')

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='accounts/password_reset_form.html'), name='password_reset_form'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),
    path('editar-perfil/', views.edit_profile, name='edit_profile'),
]
