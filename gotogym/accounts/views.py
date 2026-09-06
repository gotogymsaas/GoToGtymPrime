from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import logout, authenticate, login, get_user_model, update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q
from pathlib import Path
import hashlib
from .models import User
import os
from django.contrib.auth.decorators import login_required

TERMS_PATH = Path(__file__).resolve().parent / 'templates' / 'accounts' / 'terms_and_conditions.html'

User = get_user_model()

def logout_view(request):
    logout(request)
    return redirect('home')

@csrf_protect
def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        age = request.POST.get('age')
        email = request.POST.get('email')
        username = email  # O puedes pedir username aparte si lo deseas
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        accepted_terms = request.POST.get('accepted_terms')
        # Validaciones básicas
        if not all([first_name, last_name, age, email, password1, password2, accepted_terms]):
            messages.error(request, 'Todos los campos son obligatorios.')
        elif password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'El correo ya está registrado.')
        else:
            terms_text = TERMS_PATH.read_text(encoding='utf-8')
            user = User.objects.create_user(
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name,
                age=age,
                password=password1,
                accepted_terms=True,
                terms_accepted_at=timezone.now(),
                terms_hash=hashlib.sha512(terms_text.encode()).hexdigest(),
            )
            messages.success(request, 'Registro exitoso. Ahora puedes iniciar sesión.')
            return redirect('commercial_login')
    return render(request, 'accounts/register.html')

@csrf_protect
def login_view(request):
    return _login_response(request, 'accounts/commercial_login.html')


@csrf_protect
def commercial_login_view(request):
    return _login_response(request, 'accounts/commercial_login.html')


def _login_response(request, template_name):
    show_logo = request.session.pop('show_logo', True)
    error_message = None
    redirect_to = request.POST.get('next') or request.GET.get('next') or reverse('logged_home')
    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        user = authenticate(request, username=username_or_email, password=password)
        if user is None:
            # Intentar autenticación por email
            user_obj = User.objects.filter(
                Q(email__iexact=username_or_email) | Q(username__iexact=username_or_email)
            ).first()
            if user_obj is not None:
                user = authenticate(request, username=user_obj.get_username(), password=password)
        if user is not None:
            login(request, user)
            if not url_has_allowed_host_and_scheme(redirect_to, allowed_hosts={request.get_host()}):
                redirect_to = '/'
            return redirect(redirect_to)
        else:
            error_message = _('Credenciales incorrectas')
    return render(request, template_name, {'error_message': error_message, 'show_logo': show_logo, 'next': redirect_to})

@login_required
def edit_profile(request):
    user = request.user
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        age = request.POST.get('age', '').strip()
        email = request.POST.get('email', '').strip()
        current_password = request.POST.get('current_password', '')
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        changed = False

        if first_name and first_name != user.first_name:
            user.first_name = first_name
            changed = True
        if last_name and last_name != user.last_name:
            user.last_name = last_name
            changed = True
        if age:
            try:
                age_value = int(age)
            except ValueError:
                if is_ajax:
                    return JsonResponse({'ok': False, 'message': 'La edad debe ser un número válido.'}, status=400)
                messages.error(request, 'La edad debe ser un número válido.')
                return redirect('edit_profile')
            if age_value != user.age:
                user.age = age_value
                changed = True
        if email and email != user.email:
            User = get_user_model()
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                if is_ajax:
                    return JsonResponse({'ok': False, 'message': 'Este correo ya está registrado.'}, status=400)
                messages.error(request, 'Este correo ya está registrado.')
                return redirect('edit_profile')
            user.email = email
            changed = True
        if password:
            if password != password2:
                if is_ajax:
                    return JsonResponse({'ok': False, 'message': 'Las contraseñas no coinciden.'}, status=400)
                messages.error(request, 'Las contraseñas no coinciden.')
                return redirect('edit_profile')
            if not current_password or not check_password(current_password, user.password):
                if is_ajax:
                    return JsonResponse({'ok': False, 'message': 'La contraseña actual no es correcta.'}, status=400)
                messages.error(request, 'La contraseña actual no es correcta.')
                return redirect('edit_profile')
            user.set_password(password)
            update_session_auth_hash(request, user)
            changed = True
        if changed:
            user.save()
            if is_ajax:
                return JsonResponse({'ok': True, 'message': 'Perfil actualizado correctamente.'})
            messages.success(request, 'Perfil actualizado correctamente.')
        else:
            if is_ajax:
                return JsonResponse({'ok': True, 'message': 'No se realizaron cambios.'})
            messages.info(request, 'No se realizaron cambios.')
        return redirect('logged_home')
    return render(request, 'accounts/edit_profile.html', {'user': user})
