from decimal import Decimal
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from gotogym.tasks import enqueue

from . import correos
from .forms import (
    CAMPOS_PERSONALES,
    PayoutAccountForm,
    PerfilAfiliadoForm,
    PostulacionForm,
    RedSocialFormSet,
)
from .models import (
    CommissionStatus,
    ConfiguracionProgramaAfiliados,
    EstadoAfiliado,
    PayoutAccount,
    RecursoMarca,
    SocialNetwork,
    SocialPlatform,
    WithdrawalStatus,
)
from .services import (
    MontoMinimoError,
    aceptar_terminos_vigentes,
    anio_pedido,
    aplicar_bajas_vencidas,
    cancelar_baja,
    confirmar_comisiones_vencidas,
    deactivate_afiliado,
    fecha_limite_de_la_solicitud,
    historial_de_pagos,
    mes_pedido,
    necesita_reaceptar_terminos,
    request_withdrawal,
    saldo_para_pago,
    solicitar_baja,
    total_pagado_en_anio,
)
from .terminos import VERSION_TERMINOS_AFILIADOS, VIGENTE_DESDE

PREFIJO_REDES = 'redes'


def terminos(request):
    """Texto vigente de los terminos del programa. Publico: se lee antes de
    postularse, y desde la cuenta de pago y el pie del sitio."""
    return render(request, 'afiliados/terminos.html', {
        'version': VERSION_TERMINOS_AFILIADOS,
        'vigente_desde': VIGENTE_DESDE,
        'back_url': reverse('home'),
    })


def get_referred_orders(profile):
    """Pedidos realmente pagados que se atribuyen a este afiliado, con su
    comision si ya se genero (ver `afiliados.services.register_order_commission`)."""
    from orders.models import PaymentStatus

    return (
        profile.referred_orders
        .filter(payment_status=PaymentStatus.APPROVED)
        .select_related('commission')
        .order_by('-created_at')
    )


def _perfil(request):
    return getattr(request.user, 'perfil_afiliado', None)


def _es_aprobado(profile):
    """Fue aprobado alguna vez (aunque ya haya salido): puede ver y cobrar lo
    que le queda."""
    return profile is not None and profile.status == EstadoAfiliado.APPROVED


def _es_activo(profile):
    return _es_aprobado(profile) and profile.is_active


def _poner_al_dia(profile):
    """Avanza lo que depende del tiempo antes de mostrar o actuar: bajas con
    preaviso vencido y comisiones cuya validacion termino. Asi nada depende de
    que una tarea periodica este programada."""
    aplicar_bajas_vencidas()
    if profile is not None and profile.status == EstadoAfiliado.APPROVED:
        confirmar_comisiones_vencidas(afiliado=profile)
        profile.refresh_from_db()


def requiere_terminos_vigentes(vista):
    """Un afiliado activo debe haber aceptado la version vigente de los
    terminos antes de seguir usando su panel."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        profile = _perfil(request)
        if profile is not None and necesita_reaceptar_terminos(profile):
            return redirect('afiliado_aceptar_terminos')
        return vista(request, *args, **kwargs)
    return envoltura


def _necesita_postularse(profile):
    """Si debe ver el formulario de postulacion en lugar de su dashboard:
    no tiene perfil, lo cancelo antes, o fue rechazado."""
    return profile is None or not profile.is_active or profile.status == EstadoAfiliado.REJECTED


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
            afiliado=perfil, platform=datos['platform'], other_name=datos['other_name'],
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
    perfil.status = EstadoAfiliado.PENDING
    perfil.is_active = True
    perfil.reviewed_at = None
    perfil.reviewed_by = None
    perfil.rejection_reason = ''
    perfil.exit_requested_at = None
    perfil.exit_effective_at = None
    perfil.exited_at = None
    perfil.exit_reason = ''
    perfil.exit_notes = ''
    perfil.terms_accepted_at = ahora
    perfil.terms_version = VERSION_TERMINOS_AFILIADOS
    if era_nueva:
        perfil.user = user
    with transaction.atomic():
        perfil.save()
        _reemplazar_redes(perfil, redes)
        enqueue(correos.solicitud_recibida, perfil.pk)
    return perfil, not era_nueva


@login_required
def suscribete(request):
    user = request.user
    profile = _perfil(request)
    necesita_postularse = _necesita_postularse(profile)

    if request.method != 'POST':
        if not necesita_postularse:
            return redirect('afiliado_dashboard')
        contexto = {
            'form': PostulacionForm(instance=profile, initial=_datos_iniciales_de_postulacion(user, profile)),
            'redes': RedSocialFormSet(initial=_redes_iniciales(profile), prefix=PREFIJO_REDES),
        }
        return render(request, 'afiliados/suscribete.html', contexto)

    if not necesita_postularse:
        if profile.status == EstadoAfiliado.PENDING:
            messages.info(request, 'Tu solicitud ya esta en revision.')
        else:
            messages.info(request, 'Ya eres afiliado.')
        return redirect('afiliado_dashboard')

    formulario = PostulacionForm(request.POST, instance=profile)
    redes = RedSocialFormSet(request.POST, prefix=PREFIJO_REDES)
    # Se validan ambos antes de decidir, para mostrar todos los errores a la vez.
    formulario_valido, redes_validas = formulario.is_valid(), redes.is_valid()
    if not (formulario_valido and redes_validas):
        return render(request, 'afiliados/suscribete.html', {'form': formulario, 'redes': redes})

    try:
        _, re_postulacion = _guardar_postulacion(user, profile, formulario, redes)
    except IntegrityError:
        messages.error(request, 'Hubo un problema al enviar tu solicitud. Intenta de nuevo.')
        return redirect('afiliado_suscribete')
    if re_postulacion:
        messages.success(request, 'Tu solicitud fue enviada de nuevo. Te avisaremos cuando sea revisada.')
    else:
        messages.success(request, 'Tu solicitud fue enviada. Te avisaremos cuando sea aprobada.')
    return redirect('afiliado_dashboard')


class AceptarTerminosForm(forms.Form):
    accept_terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'Debes aceptar los terminos para seguir usando el panel.'},
    )


@login_required
def aceptar_terminos(request):
    """Quien ya era afiliado cuando cambiaron los terminos los acepta de nuevo
    con la misma casilla de la postulacion. Si prefiere no hacerlo, puede
    darse de baja sin penalizacion."""
    profile = _perfil(request)
    if profile is None or not necesita_reaceptar_terminos(profile):
        return redirect('afiliado_dashboard')
    formulario = AceptarTerminosForm(request.POST or None)
    if request.method == 'POST' and formulario.is_valid():
        aceptar_terminos_vigentes(profile)
        messages.success(request, 'Aceptaste los terminos vigentes del programa.')
        return redirect('afiliado_dashboard')
    return render(request, 'afiliados/aceptar_terminos.html', {
        'form': formulario, 'profile': profile,
        'version': VERSION_TERMINOS_AFILIADOS, 'vigente_desde': VIGENTE_DESDE,
    })


def _contexto_de_pagos(profile):
    """Lo que el afiliado necesita para entender su saldo y sus pagos."""
    confirmadas, por_recuperar, neto = saldo_para_pago(profile)
    minimo = ConfiguracionProgramaAfiliados.load().minimum_payout
    anio = timezone.localdate().year
    pendiente = profile.withdrawal_requests.filter(status=WithdrawalStatus.PENDING).first()
    cuenta = PayoutAccount.objects.filter(afiliado=profile).first()
    return {
        'pending_withdrawal': pendiente,
        'fecha_limite_de_pago': fecha_limite_de_la_solicitud(pendiente) if pendiente else None,
        'pending_commission_total': profile.commissions.filter(
            status=CommissionStatus.PENDING,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'por_recuperar': por_recuperar,
        'saldo_neto': neto,
        'minimo_de_pago': minimo,
        'falta_para_el_minimo': max(Decimal('0.00'), minimo - neto),
        'puede_solicitar': neto >= minimo and neto > 0 and pendiente is None,
        'payout_account': cuenta,
        'titular_no_coincide': cuenta is not None and not cuenta.documento_coincide_con_el_perfil,
        'anio_actual': anio,
        'pagado_en_el_anio': total_pagado_en_anio(profile, anio),
    }


@login_required
@requiere_terminos_vigentes
def dashboard(request):
    profile = _perfil(request)
    if not profile:
        return redirect('afiliado_suscribete')
    _poner_al_dia(profile)

    contexto = {'profile': profile}
    activo = _es_activo(profile)
    ex_afiliado = _es_aprobado(profile) and not profile.is_active
    if activo or ex_afiliado:
        contexto.update(_contexto_de_pagos(profile))
        contexto['ex_afiliado'] = ex_afiliado
    if activo:
        contexto['compras'] = get_referred_orders(profile)[:10]
        contexto['redes'] = list(profile.social_networks.all())
        contexto['total_seguidores'] = sum(red.followers for red in contexto['redes'])
        contexto['click_count'] = profile.referral_clicks.count()
        if contexto['click_count']:
            # Formateado como texto (no Decimal/float) para que la plantilla
            # no le aplique la localizacion regional del separador decimal.
            tasa = profile.total_referred / contexto['click_count'] * 100
            contexto['conversion_rate'] = f"{tasa:.1f}"
    return render(request, 'afiliados/dashboard.html', contexto)


@login_required
@requiere_terminos_vigentes
def editar_perfil(request):
    """Datos personales y redes sociales del afiliado, para mantenerlos al
    dia despues de postularse. Disponible mientras la postulacion siga en
    pie (pendiente o aprobada); quien fue rechazado o se dio de baja los
    actualiza al volver a postularse."""
    profile = _perfil(request)
    if profile is None or _necesita_postularse(profile):
        return redirect('afiliado_dashboard')

    # Quien ya fue aprobado cobra por Bre-B: desde aqui llega a actualizar la cuenta.
    cuenta = PayoutAccount.objects.filter(afiliado=profile).first()
    aprobado = profile.status == EstadoAfiliado.APPROVED
    if request.method != 'POST':
        contexto = {
            'form': PerfilAfiliadoForm(instance=profile),
            'redes': RedSocialFormSet(initial=_redes_iniciales(profile), prefix=PREFIJO_REDES),
            'cuenta': cuenta, 'aprobado': aprobado,
        }
        return render(request, 'afiliados/editar_perfil.html', contexto)

    formulario = PerfilAfiliadoForm(request.POST, instance=profile)
    redes = RedSocialFormSet(request.POST, prefix=PREFIJO_REDES)
    formulario_valido, redes_validas = formulario.is_valid(), redes.is_valid()
    if not (formulario_valido and redes_validas):
        contexto = {'form': formulario, 'redes': redes, 'cuenta': cuenta, 'aprobado': aprobado}
        return render(request, 'afiliados/editar_perfil.html', contexto)

    with transaction.atomic():
        formulario.save()
        _reemplazar_redes(profile, redes)
    messages.success(request, 'Tu perfil quedo actualizado.')
    return redirect('afiliado_dashboard')


@login_required
@requiere_terminos_vigentes
def compras_referidas(request):
    profile = _perfil(request)
    if not _es_activo(profile):
        return redirect('afiliado_dashboard')
    _poner_al_dia(profile)
    compras = get_referred_orders(profile)
    return render(request, 'afiliados/compras_referidas.html', {'compras': compras})


@login_required
@requiere_terminos_vigentes
def pagos(request):
    """Historial de pagos del afiliado: totales por ano y desglose por mes.
    Disponible tambien para quien ya salio del programa."""
    profile = _perfil(request)
    if not _es_aprobado(profile):
        return redirect('afiliado_dashboard')
    historial = historial_de_pagos(profile, anio_pedido(request.GET.get('anio')), mes_pedido(request.GET.get('mes')))
    return render(request, 'afiliados/pagos.html', {'profile': profile, **historial})


MAX_NOTA_DE_PAGO = 1000


@login_required
@requiere_terminos_vigentes
def cuenta_de_pago(request):
    """Inscripcion de la cuenta Bre-B donde se le pagan las comisiones. Solo
    afiliados aprobados: antes de eso no hay nada que pagar. Quien ya salio del
    programa sigue pudiendo actualizarla para cobrar lo que le queda."""
    profile = _perfil(request)
    if not _es_aprobado(profile):
        return redirect('afiliado_dashboard')

    cuenta = PayoutAccount.objects.filter(afiliado=profile).first()
    inicial = {}
    if cuenta is None:
        # Los datos personales ya se pidieron al postularse: se reutilizan.
        origen = profile if profile.first_name else request.user
        inicial = {campo: getattr(origen, campo, '') for campo in CAMPOS_PERSONALES if hasattr(origen, campo)}
    formulario = PayoutAccountForm(request.POST or None, instance=cuenta, initial=inicial)
    if request.method == 'POST' and formulario.is_valid():
        nueva = formulario.save(commit=False)
        nueva.afiliado = profile
        # La primera aceptacion se conserva; al actualizar no se pisa.
        ahora = timezone.now()
        nueva.terms_accepted_at = nueva.terms_accepted_at or ahora
        nueva.data_consent_at = nueva.data_consent_at or ahora
        nueva.save()
        if nueva.documento_coincide_con_el_perfil:
            messages.success(request, 'Tu cuenta Bre-B quedo guardada. Ya puedes solicitar tu comision.')
        else:
            messages.warning(
                request,
                'Guardamos tu cuenta Bre-B, pero el documento del titular no coincide con el de tu perfil. '
                'Los terminos piden que la cuenta sea tuya: el equipo la revisara antes de pagarte.',
            )
        return redirect('afiliado_dashboard')
    return render(request, 'afiliados/cuenta_pago.html', {'form': formulario, 'cuenta': cuenta})


@login_required
@requiere_terminos_vigentes
def solicitar_retiro(request):
    """Solicitud de comision: se paga a la cuenta Bre-B inscrita, cuyos datos
    quedan copiados en la solicitud, y el afiliado puede sumar una nota. Es
    POST: el panel muestra el formulario desplegable."""
    profile = _perfil(request)
    if not _es_aprobado(profile):
        return redirect('afiliado_dashboard')
    if request.method != 'POST':
        return redirect('afiliado_dashboard')
    if profile.withdrawal_requests.filter(status=WithdrawalStatus.PENDING).exists():
        messages.info(request, 'Ya tienes una solicitud de comision pendiente.')
        return redirect('afiliado_dashboard')

    cuenta = PayoutAccount.objects.filter(afiliado=profile).first()
    if cuenta is None:
        messages.error(request, 'Inscribe tu cuenta Bre-B antes de solicitar tu comision.')
        return redirect('afiliado_dashboard')

    nota = request.POST.get('payment_details', '').strip()
    if len(nota) > MAX_NOTA_DE_PAGO:
        messages.error(request, f'El mensaje es muy largo (maximo {MAX_NOTA_DE_PAGO} caracteres).')
        return redirect('afiliado_dashboard')

    datos_de_pago = cuenta.as_payment_details()
    if nota:
        datos_de_pago = f'{datos_de_pago}\n\nNota del afiliado: {nota}'
    try:
        solicitud = request_withdrawal(profile, datos_de_pago)
    except MontoMinimoError as error:
        messages.error(
            request,
            f'Necesitas al menos ${error.minimo:,.0f} COP en comisiones confirmadas para solicitar un pago; '
            f'tienes ${error.disponible:,.0f} COP.'.replace(',', '.'),
        )
        return redirect('afiliado_dashboard')
    if solicitud is None:
        messages.error(request, 'No tienes comisiones confirmadas disponibles para solicitar todavia.')
    else:
        limite = fecha_limite_de_la_solicitud(solicitud)
        messages.success(
            request,
            f'Solicitud de comision por ${solicitud.amount} enviada. '
            f'Se paga a mas tardar el {limite:%d/%m/%Y} (primeros 10 dias habiles del mes siguiente).',
        )
    return redirect('afiliado_dashboard')


@login_required
def quitar_suscripcion(request):
    """Baja del programa. Quien ya es afiliado debe avisar con 15 dias de
    antelacion: se registra el aviso y la baja se hace efectiva al vencer.
    Quien solo tiene una solicitud en revision la cancela de inmediato."""
    profile = _perfil(request)
    if request.method != 'POST' or not profile:
        return redirect('/')
    if _es_activo(profile):
        solicitar_baja(profile)
        messages.success(
            request,
            f'Registramos tu aviso de baja. Sera efectiva el {timezone.localtime(profile.exit_effective_at):%d/%m/%Y}; '
            'hasta entonces tu codigo y tu panel siguen activos.',
        )
        return redirect('afiliado_dashboard')
    if profile.is_active:
        deactivate_afiliado(profile)
        messages.success(request, 'Cancelaste tu participacion en el programa de afiliados.')
    return redirect('/')


@login_required
def cancelar_aviso_de_baja(request):
    profile = _perfil(request)
    if request.method == 'POST' and profile is not None and profile.baja_solicitada:
        cancelar_baja(profile)
        messages.success(request, 'Cancelaste tu aviso de baja: sigues en el programa.')
    return redirect('afiliado_dashboard')


GUIA_DE_CONTENIDO = {
    'hashtags': ['#GoToGym', '#GoToGymTeam', '#VidaSaludable'],
    'publicidad': ['#Publicidad', '#Ad', '#ColaboracionPagada'],
}


@login_required
@requiere_terminos_vigentes
def recursos(request):
    """Guia de contenido y material de marca para afiliados activos."""
    profile = _perfil(request)
    if not _es_activo(profile):
        return redirect('afiliado_dashboard')
    return render(request, 'afiliados/recursos.html', {
        'profile': profile,
        'guia': GUIA_DE_CONTENIDO,
        'recursos': RecursoMarca.objects.filter(is_active=True),
        'enlace': f'{request.scheme}://{request.get_host()}{reverse("home")}?ref={profile.referral_code}',
    })


@login_required
@requiere_terminos_vigentes
def descargar_recurso(request, pk):
    """Descarga de un recurso: solo afiliados activos, y siempre como adjunto
    (nunca se interpreta en el navegador)."""
    profile = _perfil(request)
    if not _es_activo(profile):
        raise Http404
    recurso = get_object_or_404(RecursoMarca, pk=pk, is_active=True)
    try:
        archivo = recurso.file.open('rb')
    except FileNotFoundError as error:
        raise Http404 from error
    nombre = recurso.file.name.rsplit('/', 1)[-1]
    return FileResponse(archivo, as_attachment=True, filename=nombre)

