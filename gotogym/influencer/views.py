from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import (
    CAMPOS_PERSONALES,
    PayoutAccountForm,
    PerfilAfiliadoForm,
    PostulacionForm,
    RedSocialFormSet,
)
from .models import (
    CommissionStatus,
    InfluencerStatus,
    PayoutAccount,
    SocialNetwork,
    SocialPlatform,
    WithdrawalStatus,
)
from .services import deactivate_influencer, request_withdrawal

PREFIJO_REDES = 'redes'


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


def _datos_iniciales_de_postulacion(user, profile):
    """Lo que se precarga en el formulario: lo que la persona ya dijo en una
    postulacion anterior y, si no hay, lo que ya tiene en su cuenta."""
    inicial = {'referral_code': ''}
    if profile is not None and profile.first_name:
        inicial.update({campo: getattr(profile, campo) for campo in CAMPOS_PERSONALES})
    else:
        inicial.update(first_name=user.first_name, last_name=user.last_name, phone=user.phone)
    return inicial


def _redes_iniciales(profile):
    """Instagram por defecto en una postulacion nueva; en una re-postulacion,
    las redes que la persona ya habia declarado."""
    previas = list(profile.social_networks.all()) if profile is not None else []
    if not previas:
        return [{'platform': SocialPlatform.INSTAGRAM}]
    return [
        {'platform': red.platform, 'other_name': red.other_name, 'username': red.username, 'followers': red.followers}
        for red in previas
    ]


def _reemplazar_redes(perfil, redes):
    """Deja en el perfil exactamente las redes del formulario (las filas que
    quedaron en blanco no cuentan)."""
    perfil.social_networks.all().delete()
    SocialNetwork.objects.bulk_create([
        SocialNetwork(
            influencer=perfil, platform=datos['platform'], other_name=datos['other_name'],
            username=datos['username'], followers=datos['followers'],
        )
        for datos in (red.cleaned_data for red in redes.forms)
        if datos
    ])


def _guardar_postulacion(user, profile, formulario, redes):
    """Crea el perfil pendiente (o reabre el anterior) y reemplaza sus redes
    por las del formulario. Devuelve el perfil y si era una re-postulacion."""
    ahora = timezone.now()
    perfil = formulario.save(commit=False)
    era_nueva = profile is None
    perfil.status = InfluencerStatus.PENDING
    perfil.is_active = True
    perfil.reviewed_at = None
    perfil.reviewed_by = None
    perfil.terms_accepted_at = ahora
    if era_nueva:
        perfil.user = user
    with transaction.atomic():
        perfil.save()
        _reemplazar_redes(perfil, redes)
    return perfil, not era_nueva


@login_required
def suscribete(request):
    user = request.user
    profile = getattr(user, 'influencer_profile', None)
    necesita_postularse = _necesita_postularse(profile)

    if request.method != 'POST':
        if not necesita_postularse:
            return redirect('influencer_dashboard')
        contexto = {
            'form': PostulacionForm(instance=profile, initial=_datos_iniciales_de_postulacion(user, profile)),
            'redes': RedSocialFormSet(initial=_redes_iniciales(profile), prefix=PREFIJO_REDES),
        }
        return render(request, 'influencer/suscribete.html', contexto)

    if not necesita_postularse:
        if profile.status == InfluencerStatus.PENDING:
            messages.info(request, 'Tu solicitud ya esta en revision.')
        else:
            messages.info(request, 'Ya eres afiliado.')
        return redirect('influencer_dashboard')

    formulario = PostulacionForm(request.POST, instance=profile)
    redes = RedSocialFormSet(request.POST, prefix=PREFIJO_REDES)
    # Se validan ambos antes de decidir, para mostrar todos los errores a la vez.
    formulario_valido, redes_validas = formulario.is_valid(), redes.is_valid()
    if not (formulario_valido and redes_validas):
        return render(request, 'influencer/suscribete.html', {'form': formulario, 'redes': redes})

    try:
        _, re_postulacion = _guardar_postulacion(user, profile, formulario, redes)
    except IntegrityError:
        messages.error(request, 'Hubo un problema al enviar tu solicitud. Intenta de nuevo.')
        return redirect('influencer_suscribete')
    if re_postulacion:
        messages.success(request, 'Tu solicitud fue enviada de nuevo. Te avisaremos cuando sea revisada.')
    else:
        messages.success(request, 'Tu solicitud fue enviada. Te avisaremos cuando sea aprobada.')
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
        contexto['payout_account'] = PayoutAccount.objects.filter(influencer=profile).first()
        contexto['redes'] = list(profile.social_networks.all())
        contexto['total_seguidores'] = sum(red.followers for red in contexto['redes'])
        contexto['click_count'] = profile.referral_clicks.count()
        if contexto['click_count']:
            # Formateado como texto (no Decimal/float) para que la plantilla
            # no le aplique la localizacion regional del separador decimal.
            tasa = profile.total_referred / contexto['click_count'] * 100
            contexto['conversion_rate'] = f"{tasa:.1f}"
    return render(request, 'influencer/dashboard.html', contexto)


@login_required
def editar_perfil(request):
    """Datos personales y redes sociales del afiliado, para mantenerlos al
    dia despues de postularse. Disponible mientras la postulacion siga en
    pie (pendiente o aprobada); quien fue rechazado o se dio de baja los
    actualiza al volver a postularse."""
    profile = getattr(request.user, 'influencer_profile', None)
    if profile is None or _necesita_postularse(profile):
        return redirect('influencer_dashboard')

    if request.method != 'POST':
        contexto = {
            'form': PerfilAfiliadoForm(instance=profile),
            'redes': RedSocialFormSet(initial=_redes_iniciales(profile), prefix=PREFIJO_REDES),
        }
        return render(request, 'influencer/editar_perfil.html', contexto)

    formulario = PerfilAfiliadoForm(request.POST, instance=profile)
    redes = RedSocialFormSet(request.POST, prefix=PREFIJO_REDES)
    formulario_valido, redes_validas = formulario.is_valid(), redes.is_valid()
    if not (formulario_valido and redes_validas):
        return render(request, 'influencer/editar_perfil.html', {'form': formulario, 'redes': redes})

    with transaction.atomic():
        formulario.save()
        _reemplazar_redes(profile, redes)
    messages.success(request, 'Tu perfil quedo actualizado.')
    return redirect('influencer_dashboard')


@login_required
def compras_referidas(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile or profile.status != InfluencerStatus.APPROVED or not profile.is_active:
        return redirect('influencer_dashboard')
    compras = get_referred_orders(profile)
    return render(request, 'influencer/compras_referidas.html', {'compras': compras})


MAX_NOTA_DE_PAGO = 1000


@login_required
def cuenta_de_pago(request):
    """Inscripcion de la cuenta Bre-B donde se le pagan las comisiones. Solo
    afiliados aprobados: antes de eso no hay nada que pagar."""
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile or profile.status != InfluencerStatus.APPROVED or not profile.is_active:
        return redirect('influencer_dashboard')

    cuenta = PayoutAccount.objects.filter(influencer=profile).first()
    inicial = {}
    if cuenta is None:
        # Los datos personales ya se pidieron al postularse: se reutilizan.
        origen = profile if profile.first_name else request.user
        inicial = {campo: getattr(origen, campo, '') for campo in CAMPOS_PERSONALES if hasattr(origen, campo)}
    formulario = PayoutAccountForm(request.POST or None, instance=cuenta, initial=inicial)
    if request.method == 'POST' and formulario.is_valid():
        nueva = formulario.save(commit=False)
        nueva.influencer = profile
        nueva.terms_accepted_at = nueva.data_consent_at = timezone.now()
        nueva.save()
        messages.success(request, 'Tu cuenta Bre-B quedo guardada. Ya puedes solicitar tu comision.')
        return redirect('influencer_dashboard')
    return render(request, 'influencer/cuenta_pago.html', {'form': formulario, 'cuenta': cuenta})


@login_required
def solicitar_retiro(request):
    """Solicitud de comision: se paga a la cuenta Bre-B inscrita, cuyos datos
    quedan copiados en la solicitud, y el afiliado puede sumar una nota. Es
    POST: el panel muestra el formulario desplegable."""
    profile = getattr(request.user, 'influencer_profile', None)
    if not profile or profile.status != InfluencerStatus.APPROVED or not profile.is_active:
        return redirect('influencer_dashboard')
    if request.method != 'POST':
        return redirect('influencer_dashboard')
    if profile.withdrawal_requests.filter(status=WithdrawalStatus.PENDING).exists():
        messages.info(request, 'Ya tienes una solicitud de comision pendiente.')
        return redirect('influencer_dashboard')

    cuenta = PayoutAccount.objects.filter(influencer=profile).first()
    if cuenta is None:
        messages.error(request, 'Inscribe tu cuenta Bre-B antes de solicitar tu comision.')
        return redirect('influencer_dashboard')

    nota = request.POST.get('payment_details', '').strip()
    if len(nota) > MAX_NOTA_DE_PAGO:
        messages.error(request, f'El mensaje es muy largo (maximo {MAX_NOTA_DE_PAGO} caracteres).')
        return redirect('influencer_dashboard')

    datos_de_pago = cuenta.as_payment_details()
    if nota:
        datos_de_pago = f'{datos_de_pago}\n\nNota del afiliado: {nota}'
    solicitud = request_withdrawal(profile, datos_de_pago)
    if solicitud is None:
        messages.error(request, 'No tienes comisiones disponibles para solicitar todavia.')
    else:
        messages.success(
            request,
            f'Solicitud de comision por ${solicitud.amount} enviada. Te responderemos con la mayor brevedad posible.',
        )
    return redirect('influencer_dashboard')


@login_required
def quitar_suscripcion(request):
    profile = getattr(request.user, 'influencer_profile', None)
    if profile:
        deactivate_influencer(profile)
        messages.success(request, 'Cancelaste tu participacion en el programa de afiliados.')
    return redirect('/')
