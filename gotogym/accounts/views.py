from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import logout, authenticate, login, get_user_model
from django.contrib import messages
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponseRedirect
from django.utils import timezone
from pathlib import Path
import hashlib
from .models import User
import os
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.urls import reverse

TERMS_PATH = Path(__file__).resolve().parent / 'templates' / 'accounts' / 'terms_and_conditions.html'

User = get_user_model()

def logout_view(request):
    logout(request)
    return redirect('/')

@csrf_protect
def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        age = request.POST.get('age')
        email = request.POST.get('email')
        # Autocompletar username con la parte antes del @
        username = email.split('@')[0] if email else ''
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
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está registrado.')
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
            messages.success(request, f'Registro exitoso. Tu usuario es: {username}. Ahora puedes iniciar sesión.')
            return redirect('login')
    return render(request, 'accounts/register.html')

@csrf_protect
def login_view(request):
    show_logo = request.session.pop('show_logo', True)
    error_message = None
    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        # Buscar usuario por username o email
        try:
            user_obj = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            try:
                user_obj = User.objects.get(email=username_or_email)
            except User.DoesNotExist:
                user_obj = None
        user = None
        if user_obj:
            user = authenticate(request, username=user_obj.email, password=password)
        if user is not None:
            # Si es admin y le falta nombre o apellido, redirigir a editar perfil
            if user.is_superuser and (not user.first_name or not user.last_name or user.first_name == 'None' or user.last_name == 'None'):
                login(request, user)
                return redirect(reverse('edit_profile'))
            login(request, user)
            return redirect('/')
        else:
            error_message = _('Credenciales incorrectas')
    return render(request, 'accounts/login.html', {'error_message': error_message, 'show_logo': show_logo})

@login_required
def edit_profile(request):
    user = request.user
    force_edit = False
    if user.is_superuser and (not user.first_name or not user.last_name or user.first_name == 'None' or user.last_name == 'None'):
        force_edit = True
        messages.warning(request, 'Por favor, completa tu nombre y apellido para continuar.')
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        changed = False
        if first_name and first_name != user.first_name:
            user.first_name = first_name
            changed = True
        if last_name and last_name != user.last_name:
            user.last_name = last_name
            changed = True
        if email and email != user.email:
            user.email = email
            changed = True
        if password:
            user.set_password(password)
            update_session_auth_hash(request, user)
            changed = True
        if changed:
            user.save()
            messages.success(request, 'Perfil actualizado correctamente.')
        else:
            messages.info(request, 'No se realizaron cambios.')
        return redirect('edit_profile')
    return render(request, 'accounts/edit_profile.html', {'user': user, 'force_edit': force_edit})

@login_required
def profile_view(request):
    return render(request, 'accounts/profile_view.html', {'user': request.user})
