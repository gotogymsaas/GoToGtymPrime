from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import InfluencerProfile
from django.db import IntegrityError

# Simulación de compras referidas (reemplazar por consulta real a modelo de compras)
def get_compras_referidas(profile):
    # Aquí deberías consultar tu modelo de compras real
    return [
        {'nombre': 'Ana Pérez', 'email': 'ana@email.com', 'fecha': '2025-06-01', 'monto': 120000},
        {'nombre': 'Luis Gómez', 'email': 'luis@email.com', 'fecha': '2025-06-15', 'monto': 85000},
    ]

@login_required
def suscribete(request):
    user = request.user
    if hasattr(user, 'influencer_profile'):
        messages.info(request, 'Ya eres influencer.')
        return redirect('influencer_dashboard')
    try:
        InfluencerProfile.objects.create(user=user)
        messages.success(request, '¡Ahora eres influencer!')
    except IntegrityError:
        messages.error(request, 'Hubo un problema al suscribirte. Intenta de nuevo.')
    return redirect('influencer_dashboard')

@login_required
def dashboard(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile:
        return redirect('influencer_suscribete')
    compras = get_compras_referidas(profile)
    return render(request, 'influencer/dashboard.html', {'profile': profile, 'compras': compras})

@login_required
def compras_referidas(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile:
        return redirect('influencer_suscribete')
    compras = get_compras_referidas(profile)
    return render(request, 'influencer/compras_referidas.html', {'compras': compras})

@login_required
def solicitar_retiro(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile:
        return redirect('influencer_suscribete')
    # Aquí puedes agregar lógica para procesar la solicitud de retiro
    messages.success(request, 'Solicitud de retiro enviada. Pronto nos pondremos en contacto.')
    return redirect('influencer_dashboard')

@login_required
def quitar_suscripcion(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if profile:
        profile.delete()
        messages.success(request, 'Has cancelado tu suscripción de influencer.')
    return redirect('/')
