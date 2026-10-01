from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import CommissionStatus, InfluencerProfile, InfluencerStatus, WithdrawalStatus
from .services import deactivate_influencer, request_withdrawal


def get_referred_orders(profile):
    """Pedidos realmente pagados que se atribuyen a este afiliado, con su
    comision si ya se genero (ver `influencer.services.register_order_commission`)."""
    from orders.models import PaymentStatus

    return (
        profile.referred_orders
        .filter(payment_status=PaymentStatus.APPROVED)
        .select_related('commission')
        .order_by('-created_at')
    )


def _necesita_postularse(profile):
    """Si debe ver el formulario de postulacion en lugar de su dashboard:
    no tiene perfil, lo cancelo antes, o fue rechazado."""
    return profile is None or not profile.is_active or profile.status == InfluencerStatus.REJECTED


@login_required
def suscribete(request):
    user = request.user
    profile = getattr(user, 'influencer_profile', None)

    if request.method != 'POST':
        if not _necesita_postularse(profile):
            return redirect('influencer_dashboard')
        return render(request, 'influencer/suscribete.html', {})

    if not request.POST.get('accept_terms'):
        messages.error(request, 'Debes aceptar los terminos del programa para continuar.')
        return redirect('influencer_suscribete')

    ahora = timezone.now()

    if profile is not None:
        if not profile.is_active:
            profile.is_active = True
            profile.status = InfluencerStatus.PENDING
            profile.reviewed_at = None
            profile.reviewed_by = None
            profile.terms_accepted_at = ahora
            profile.save(update_fields=[
                'is_active', 'status', 'reviewed_at', 'reviewed_by', 'terms_accepted_at',
            ])
            messages.success(request, 'Tu solicitud fue enviada de nuevo. Te avisaremos cuando sea revisada.')
        elif profile.status == InfluencerStatus.REJECTED:
            profile.status = InfluencerStatus.PENDING
            profile.reviewed_at = None
            profile.reviewed_by = None
            profile.terms_accepted_at = ahora
            profile.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'terms_accepted_at'])
            messages.success(request, 'Tu solicitud fue enviada de nuevo. Te avisaremos cuando sea revisada.')
        elif profile.status == InfluencerStatus.PENDING:
            messages.info(request, 'Tu solicitud ya esta en revision.')
        else:
            messages.info(request, 'Ya eres influencer.')
        return redirect('influencer_dashboard')

    try:
        InfluencerProfile.objects.create(
            user=user, status=InfluencerStatus.PENDING, terms_accepted_at=ahora,
        )
        messages.success(request, 'Tu solicitud fue enviada. Te avisaremos cuando sea aprobada.')
    except IntegrityError:
        messages.error(request, 'Hubo un problema al enviar tu solicitud. Intenta de nuevo.')
    return redirect('influencer_dashboard')


@login_required
def dashboard(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile:
        return redirect('influencer_suscribete')

    contexto = {'profile': profile}
    if profile.status == InfluencerStatus.APPROVED and profile.is_active:
        contexto['compras'] = get_referred_orders(profile)[:10]
        contexto['pending_withdrawal'] = profile.withdrawal_requests.filter(
            status=WithdrawalStatus.PENDING,
        ).first()
        contexto['pending_commission_total'] = profile.commissions.filter(
            status=CommissionStatus.PENDING,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        contexto['click_count'] = profile.referral_clicks.count()
        if contexto['click_count']:
            # Formateado como texto (no Decimal/float) para que la plantilla
            # no le aplique la localizacion regional del separador decimal.
            tasa = profile.total_referred / contexto['click_count'] * 100
            contexto['conversion_rate'] = f"{tasa:.1f}"
    return render(request, 'influencer/dashboard.html', contexto)


@login_required
def compras_referidas(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile or profile.status != InfluencerStatus.APPROVED or not profile.is_active:
        return redirect('influencer_dashboard')
    compras = get_referred_orders(profile)
    return render(request, 'influencer/compras_referidas.html', {'compras': compras})


@login_required
def solicitar_retiro(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile or profile.status != InfluencerStatus.APPROVED or not profile.is_active:
        return redirect('influencer_dashboard')
    if profile.withdrawal_requests.filter(status=WithdrawalStatus.PENDING).exists():
        messages.info(request, 'Ya tienes una solicitud de retiro pendiente.')
        return redirect('influencer_dashboard')

    solicitud = request_withdrawal(profile)
    if solicitud is None:
        messages.error(request, 'No tienes comisiones disponibles para retirar todavia.')
    else:
        messages.success(
            request,
            f'Solicitud de retiro por ${solicitud.amount} enviada. Te avisaremos cuando se procese.',
        )
    return redirect('influencer_dashboard')


@login_required
def quitar_suscripcion(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if profile:
        deactivate_influencer(profile)
        messages.success(request, 'Has cancelado tu suscripcion de influencer.')
    return redirect('/')
