from django.urls import path

from .views import ForgotPasswordView, ResetPasswordView, ResetPasswordSuccessView

urlpatterns = [
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/reset-password/<uuid:token>/', ResetPasswordView.as_view(), name='reset-password'),
    path('auth/reset-success/', ResetPasswordSuccessView.as_view(), name='password-reset-success'),
]
