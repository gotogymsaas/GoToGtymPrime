import hashlib
from pathlib import Path
from urllib.parse import urlparse

from carrito.services import (
    CART_VERSION,
    SESSION_CART_KEY,
    SESSION_VERSION_KEY,
    build_cart_context,
)
from django.contrib import messages
from django.contrib.auth import (
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect

from .forms import CustomerAddressForm
from .models import CustomerAddress

TERMS_PATH = Path(__file__).resolve().parent / 'templates' / 'accounts' / 'terms_and_conditions.html'

# get_user_model(), no un import directo de .models: es lo que respeta
# AUTH_USER_MODEL si algun dia cambia, y antes habia ambas cosas (un import
# de .models.User que get_user_model() pisaba dos lineas mas abajo sin que
# nada lo usara).
User = get_user_model()

def logout_view(request):
    next_url = request.POST.get('next') or request.GET.get('next')
    logout(request)
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('home')

def _es_pantalla_de_cuenta(url):
    """Entrar o registrarse no es un destino: el menu pone `next` con la pagina
    actual, y desde el login eso devolveria a quien acaba de entrar al login."""
    ruta = urlparse(url).path
    return ruta in {reverse(nombre) for nombre in ('commercial_login', 'login', 'register')}


def _safe_next_url(request, fallback):
    """`next` recibido por POST o GET si apunta a este mismo sitio."""
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if (
        next_url
        and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})
        and not _es_pantalla_de_cuenta(next_url)
    ):
        return next_url
    return fallback


def _resumen_carrito(request):
    """Lo que hay en el carrito, para mostrarlo junto al formulario de
    entrar o registrarse. Solo lee: no limpia ni reinicia el carrito de la
    sesion (eso lo hace la vista del carrito, que avisa al usuario).
    `None` si esta vacio."""
    if request.session.get(SESSION_VERSION_KEY) != CART_VERSION:
        return None
    cart = request.session.get(SESSION_CART_KEY) or {}
    if not cart:
        return None
    resumen = build_cart_context(cart)
    return resumen if resumen['items'] else None


@csrf_protect
def register_view(request):
    valores = {}
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        age = request.POST.get('age', '').strip()
        email = request.POST.get('email', '').strip()
        username = email  # O puedes pedir username aparte si lo deseas
        password1 = request.POST.get('password1', '')
        # La confirmacion es opcional: el formulario muestra un boton para ver
        # la contrasena en vez de pedirla dos veces. Si llega, debe coincidir.
        password2 = request.POST.get('password2')
        accepted_terms = request.POST.get('accepted_terms')
        valores = {'first_name': first_name, 'email': email}
        # Solo hacen falta nombre, correo, contrasena y los terminos; el
        # apellido y la edad se completan despues en "Editar perfil".
        if not all([first_name, email, password1, accepted_terms]):
            messages.error(request, 'Completa tu nombre, correo y contraseña, y acepta los términos.')
        elif password2 is not None and password1 != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
        elif age and not age.isdigit():
            messages.error(request, 'La edad debe ser un número válido.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'El correo ya está registrado.')
        else:
            terms_text = TERMS_PATH.read_text(encoding='utf-8')
            user = User.objects.create_user(
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name,
                age=int(age) if age else None,
                password=password1,
                accepted_terms=True,
                terms_accepted_at=timezone.now(),
                terms_hash=hashlib.sha512(terms_text.encode()).hexdigest(),
            )
            # Quien se registra durante una compra no debe volver a escribir
            # sus datos en el login: queda con sesion y sigue a donde iba.
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Registro exitoso. Ya iniciaste sesión.')
            return redirect(_safe_next_url(request, reverse('home')))
    return render(request, 'accounts/register.html', {
        'next': _safe_next_url(request, ''),
        'valores': valores,
        'resumen_carrito': _resumen_carrito(request),
    })

@csrf_protect
def login_view(request):
    return _login_response(request, 'accounts/commercial_login.html')


@csrf_protect
def commercial_login_view(request):
    return _login_response(request, 'accounts/commercial_login.html')


def _login_response(request, template_name):
    show_logo = request.session.pop('show_logo', True)
    error_message = None
    redirect_to = request.POST.get('next') or request.GET.get('next') or reverse('home')
    if _es_pantalla_de_cuenta(redirect_to):
        redirect_to = reverse('home')
    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        user = None
        if user is None:
            # Intentar autenticación por email
            user_obj = User.objects.filter(
                Q(email__iexact=username_or_email) | Q(username__iexact=username_or_email)
            ).first()
            if user_obj is not None and user_obj.is_active and user_obj.check_password(password):
                user = user_obj
        if user is not None:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            if not url_has_allowed_host_and_scheme(redirect_to, allowed_hosts={request.get_host()}):
                redirect_to = '/'
            return redirect(redirect_to)
        else:
            error_message = _('Credenciales incorrectas')
    # Aviso solo cuando el login viene de intentar pagar.
    checkout_notice = redirect_to.startswith(reverse('orders:checkout'))
    return render(request, template_name, {
        'error_message': error_message,
        'show_logo': show_logo,
        'next': redirect_to,
        'checkout_notice': checkout_notice,
        'resumen_carrito': _resumen_carrito(request),
    })

@login_required
def edit_profile(request):
    user = request.user
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        age = request.POST.get('age', '').strip()
        phone = request.POST.get('phone', '').strip()
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
        if phone != user.phone:
            user.phone = phone
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
        return redirect('home')
    from orders.colombia_data import MUNICIPIOS_POR_DEPARTAMENTO

    direcciones = user.addresses.all()
    direcciones_formularios = [
        {'direccion': direccion, 'form': CustomerAddressForm(instance=direccion)}
        for direccion in direcciones
    ]
    context = {
        'user': user,
        'direcciones_formularios': direcciones_formularios,
        'address_form': CustomerAddressForm(),
        'municipios_por_departamento': MUNICIPIOS_POR_DEPARTAMENTO,
    }
    return render(request, 'accounts/edit_profile.html', context)


@login_required
def address_book(request):
    return redirect('edit_profile')


@login_required
def address_edit(request, pk=None):
    direccion = get_object_or_404(CustomerAddress, pk=pk, user=request.user) if pk else None
    if request.method == 'POST':
        form = CustomerAddressForm(request.POST, instance=direccion)
        if form.is_valid():
            es_nueva = direccion is None
            nueva = form.save(commit=False)
            nueva.user = request.user
            # `full_name`/`phone` ya no se piden en este formulario (ver
            # CustomerAddressForm): una direccion es el lugar de entrega, el
            # contacto es el del perfil. Se completan aqui para no dejar
            # esas columnas vacias (las usa el precargado del checkout).
            if not nueva.full_name:
                nueva.full_name = request.user.get_full_name() or request.user.email
            if not nueva.phone:
                nueva.phone = request.user.phone
            # La predeterminada ahora se elige desde la lista de
            # direcciones (un radio por direccion), no al crear/editar una
            # sola -- salvo la primera direccion del usuario, que se marca
            # predeterminada automaticamente para que nunca quede en cero.
            if es_nueva and not request.user.addresses.exists():
                nueva.is_default = True
            nueva.save()
            messages.success(request, 'Direccion guardada.')
            return redirect('edit_profile')
    else:
        form = CustomerAddressForm(instance=direccion)
    from orders.colombia_data import MUNICIPIOS_POR_DEPARTAMENTO

    context = {
        'form': form,
        'direccion': direccion,
        'municipios_por_departamento': MUNICIPIOS_POR_DEPARTAMENTO,
    }
    return render(request, 'accounts/address_form.html', context)


@login_required
def address_delete(request, pk):
    direccion = get_object_or_404(CustomerAddress, pk=pk, user=request.user)
    if request.method == 'POST':
        direccion.delete()
        messages.success(request, 'Direccion eliminada.')
    return redirect('edit_profile')


@login_required
def address_set_default(request, pk):
    direccion = get_object_or_404(CustomerAddress, pk=pk, user=request.user)
    if request.method == 'POST':
        request.user.addresses.exclude(pk=direccion.pk).update(is_default=False)
        direccion.is_default = True
        direccion.save(update_fields=['is_default'])
        messages.success(request, 'Direccion marcada como predeterminada.')
    return redirect('edit_profile')
