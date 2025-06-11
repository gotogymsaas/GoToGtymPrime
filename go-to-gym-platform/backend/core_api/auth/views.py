from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from .models import PasswordResetToken
from .serializers import ForgotPasswordSerializer, ResetPasswordSerializer


class ForgotPasswordView(View):
    """Solicita un correo de recuperación de contraseña"""

    def get(self, request):
        return render(request, 'auth/forgot_password.html')

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.POST)
        if serializer.is_valid():
            User = get_user_model()
            try:
                user = User.objects.get(email=serializer.validated_data['email'])
            except User.DoesNotExist:
                return render(request, 'auth/forgot_password.html', {'error': 'No se encontró el usuario'})

            token = PasswordResetToken.objects.create(user=user)
            reset_link = f"https://gotogym.com/auth/reset-password/{token.token}/"
            html_message = render_to_string(
                'emails/password_reset_email.html', {'reset_link': reset_link}
            )
            send_mail(
                'Recupera tu contraseña en GoToGym',
                f'Visita {reset_link} para restablecer tu contraseña',
                'support@gotogym.store',
                [user.email],
                html_message=html_message,
            )
            return render(request, 'auth/forgot_password.html', {'message': 'Revisa tu correo para continuar'})
        return render(request, 'auth/forgot_password.html', {'errors': serializer.errors})


class ResetPasswordView(View):
    """Valida el token y actualiza la contraseña"""

    def get(self, request, token):
        token_obj = PasswordResetToken.objects.filter(token=token, is_used=False).first()
        if not token_obj or token_obj.expires_at < timezone.now():
            return render(request, 'auth/reset_password.html', {'invalid': True})
        return render(request, 'auth/reset_password.html', {'token': token})

    def post(self, request, token):
        token_obj = get_object_or_404(PasswordResetToken, token=token, is_used=False)
        if token_obj.expires_at < timezone.now():
            return render(request, 'auth/reset_password.html', {'invalid': True})
        serializer = ResetPasswordSerializer(data=request.POST)
        if serializer.is_valid():
            user = token_obj.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            token_obj.is_used = True
            token_obj.save()
            # invalidate sessions
            for session in Session.objects.filter(expire_date__gte=timezone.now()):
                data = session.get_decoded()
                if str(user.pk) == str(data.get('_auth_user_id')):
                    session.delete()
            return redirect('password-reset-success')
        return render(request, 'auth/reset_password.html', {'token': token, 'errors': serializer.errors})


class ResetPasswordSuccessView(View):
    def get(self, request):
        return render(request, 'auth/reset_success.html')
