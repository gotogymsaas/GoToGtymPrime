"""Programa de afiliados del panel: afiliados, comisiones y retiros."""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from afiliados.models import (
    Commission,
    CommissionStatus,
    ConfiguracionProgramaAfiliados,
    EstadoAfiliado,
    MotivoSalida,
    PerfilAfiliado,
    WithdrawalRequest,
    WithdrawalStatus,
)
from afiliados.services import (
    afiliados_inactivos,
    anio_pedido,
    anular_comision,
    aplicar_bajas_vencidas,
    approve_afiliado,
    avisar_afiliados,
    avisar_cambio_de_tasa,
    confirmar_comisiones_vencidas,
    deactivate_afiliado,
    extender_validacion,
    fecha_limite_de_la_solicitud,
    historial_de_pagos,
    liberar_revision,
    mes_pedido,
    reject_afiliado,
    resolve_withdrawal,
    saldo_para_pago,
    total_pagado_en_anio,
    ultima_actividad,
)
from afiliados.terminos import COMISION_GLOBAL_EN_TERMINOS
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import (
    AfiliadoCommissionRateForm,
    ConfiguracionProgramaAfiliadosForm,
    TerminacionAfiliadoForm,
)
from ..permissions import (
    require_perms,
    staff_required,
)
from ._comun import _safe_redirect


def _poner_al_dia_afiliados():
    """Avanza lo que depende del tiempo antes de mostrar el programa, sin
    depender de que haya una tarea periodica programada."""
    aplicar_bajas_vencidas()
    confirmar_comisiones_vencidas()


@staff_required
def afiliados_list(request):
    """Pagina unica del programa de afiliados: antes "Afiliados" y "Retiros
    de afiliados" vivian en pantallas separadas aunque un retiro no se
    entiende sin ver primero al afiliado que lo pide. Ahora la info de
    afiliados va arriba y los retiros abajo, en la misma pagina."""
    _poner_al_dia_afiliados()
    status = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()
    inactivos = request.GET.get("inactivos") == "1"
    profiles = PerfilAfiliado.objects.select_related("user").order_by("-created_at")
    ultima_actividad_de = {}
    if inactivos:
        encontrados = afiliados_inactivos()
        ultima_actividad_de = {perfil.pk: ultima for perfil, ultima in encontrados}
        profiles = profiles.filter(pk__in=list(ultima_actividad_de))
    elif status in dict(EstadoAfiliado.choices):
        profiles = profiles.filter(status=status)
    if query:
        profiles = profiles.filter(
            Q(user__email__icontains=query) | Q(referral_code__icontains=query.upper())
        )

    paginator = Paginator(profiles, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    if inactivos:
        for perfil in page_obj:
            perfil.ultima_actividad = ultima_actividad_de.get(perfil.pk)

    settings_form = None
    if request.user.has_perm("afiliados.change_configuracionprogramaafiliados"):
        settings_form = ConfiguracionProgramaAfiliadosForm(instance=ConfiguracionProgramaAfiliados.load())

    withdrawal_status = request.GET.get("wstatus", WithdrawalStatus.PENDING).strip()
    withdrawals_qs = WithdrawalRequest.objects.select_related("afiliado__user").order_by("-requested_at")
    if withdrawal_status in dict(WithdrawalStatus.choices):
        withdrawals_qs = withdrawals_qs.filter(status=withdrawal_status)
    withdrawal_paginator = Paginator(withdrawals_qs, 20)
    withdrawal_page_obj = withdrawal_paginator.get_page(request.GET.get("wpage"))
    for solicitud in withdrawal_page_obj:
        solicitud.fecha_limite = fecha_limite_de_la_solicitud(solicitud)

    return render(
        request,
        "administracion/afiliados.html",
        {
            "page_obj": page_obj,
            "query": query,
            "status": status,
            "inactivos": inactivos,
            "tasa_en_terminos": COMISION_GLOBAL_EN_TERMINOS,
            "tasa_difiere_de_los_terminos": (
                ConfiguracionProgramaAfiliados.load().default_commission_rate != COMISION_GLOBAL_EN_TERMINOS
            ),
            "settings_form": settings_form,
            "withdrawal_page_obj": withdrawal_page_obj,
            "withdrawal_status": withdrawal_status,
            "en_revision": Commission.objects.filter(status=CommissionStatus.PENDING, needs_review=True).count(),
        },
    )


@require_perms("afiliados.change_configuracionprogramaafiliados")
@require_POST
def afiliado_settings_update(request):
    configuracion = ConfiguracionProgramaAfiliados.load()
    tasa_anterior = configuracion.default_commission_rate
    form = ConfiguracionProgramaAfiliadosForm(request.POST, instance=configuracion)
    if form.is_valid():
        form.save()
        mensaje = "Configuración del programa de afiliados actualizada."
        if configuracion.default_commission_rate != tasa_anterior:
            avisados = avisar_cambio_de_tasa(configuracion.default_commission_rate)
            mensaje += f" Se avisó del cambio de comisión a {avisados} afiliado(s) con la tasa global."
        messages.success(request, mensaje)
    else:
        messages.error(request, "No se pudo guardar la configuración.")
    return redirect("admin_afiliados")


@staff_required
def afiliado_detail(request, pk):
    profile = get_object_or_404(PerfilAfiliado.objects.select_related("user", "reviewed_by"), pk=pk)
    _poner_al_dia_afiliados()
    profile.refresh_from_db()
    commissions = profile.commissions.select_related("order").order_by("-created_at")[:50]
    redes = list(profile.social_networks.all())
    click_count = profile.referral_clicks.count()
    conversion_rate = f"{profile.total_referred / click_count * 100:.1f}" if click_count else None
    cuenta = getattr(profile, "payout_account", None)
    anio = timezone.localdate().year
    confirmadas, por_recuperar, neto = saldo_para_pago(profile)
    return render(
        request,
        "administracion/afiliado_detail.html",
        {
            "profile": profile,
            "commissions": commissions,
            "coupons": profile.coupons.order_by("-created_at"),
            "withdrawal_requests": profile.withdrawal_requests.order_by("-requested_at"),
            "redes": redes,
            "total_seguidores": sum(red.followers for red in redes),
            "click_count": click_count,
            "conversion_rate": conversion_rate,
            "anio_actual": anio,
            "pagado_en_el_anio": total_pagado_en_anio(profile, anio),
            "por_recuperar": por_recuperar,
            "saldo_neto": neto,
            "ultima_actividad": ultima_actividad(profile),
            "titular_no_coincide": cuenta is not None and not cuenta.documento_coincide_con_el_perfil,
            "terminacion_form": TerminacionAfiliadoForm(),
            "es_aprobado_activo": profile.status == EstadoAfiliado.APPROVED and profile.is_active,
        },
    )


@staff_required
def afiliado_pagos(request, pk):
    """Historial de pagos de un afiliado: totales por ano y desglose por mes.
    Vive en su propia pantalla para no cargar el listado con una columna."""
    profile = get_object_or_404(PerfilAfiliado.objects.select_related("user"), pk=pk)
    historial = historial_de_pagos(profile, anio_pedido(request.GET.get("anio")), mes_pedido(request.GET.get("mes")))
    return render(request, "administracion/afiliado_pagos.html", {"profile": profile, **historial})


@require_perms("afiliados.change_perfilafiliado")
@require_POST
def afiliado_commission_rate_update(request, pk):
    profile = get_object_or_404(PerfilAfiliado, pk=pk)
    tasa_anterior = profile.commission_rate
    form = AfiliadoCommissionRateForm(request.POST, instance=profile)
    if form.is_valid():
        form.save()
        mensaje = "Tasa de comisión actualizada."
        if profile.commission_rate != tasa_anterior and profile.status == EstadoAfiliado.APPROVED and profile.is_active:
            nueva = profile.commission_rate if profile.commission_rate is not None else (
                ConfiguracionProgramaAfiliados.load().default_commission_rate
            )
            avisar_cambio_de_tasa(nueva, afiliado=profile)
            mensaje += " Se avisó al afiliado por correo."
        messages.success(request, mensaje)
    else:
        messages.error(request, "No se pudo guardar la tasa de comisión.")
    return redirect("admin_afiliado_detail", pk=pk)


@require_perms("afiliados.change_perfilafiliado")
@require_POST
def afiliado_notes_update(request, pk):
    profile = get_object_or_404(PerfilAfiliado, pk=pk)
    profile.review_notes = request.POST.get("review_notes", "").strip()[:2000]
    profile.save(update_fields=["review_notes"])
    messages.success(request, "Notas de revisión guardadas.")
    return redirect("admin_afiliado_detail", pk=pk)


@require_perms("afiliados.change_perfilafiliado")
@require_POST
def afiliado_approve(request, pk):
    profile = get_object_or_404(PerfilAfiliado, pk=pk)
    approve_afiliado(profile, request.user)
    messages.success(request, f"Afiliado {profile.user.email} aprobado.")
    return _safe_redirect(request, "admin_afiliados")


@require_perms("afiliados.change_perfilafiliado")
@require_POST
def afiliado_reject(request, pk):
    """El motivo es obligatorio: se le comunica al postulante."""
    profile = get_object_or_404(PerfilAfiliado, pk=pk)
    motivo = request.POST.get("reason", "").strip()
    if not motivo:
        messages.error(request, "Indica el motivo del rechazo: se le comunica al postulante.")
        return _safe_redirect(request, "admin_afiliados")
    reject_afiliado(profile, request.user, motivo)
    messages.success(request, f"Solicitud de {profile.user.email} rechazada.")
    return _safe_redirect(request, "admin_afiliados")


@require_perms("afiliados.change_perfilafiliado")
@require_POST
def afiliado_deactivate(request, pk):
    """Desactiva a un afiliado sin motivo de sancion (por ejemplo, una
    solicitud cancelada). Para terminar a alguien por incumplimiento se usa
    `afiliado_terminate`."""
    profile = get_object_or_404(PerfilAfiliado, pk=pk)
    deactivate_afiliado(profile)
    messages.success(request, f"Afiliado {profile.user.email} desactivado.")
    return _safe_redirect(request, "admin_afiliados")


@require_perms("afiliados.change_perfilafiliado")
@require_POST
def afiliado_terminate(request, pk):
    """Terminacion por parte de GoToGym: motivo obligatorio, correo al
    afiliado y, si se pide, anulacion de sus comisiones sin pagar."""
    profile = get_object_or_404(PerfilAfiliado, pk=pk)
    form = TerminacionAfiliadoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indica el motivo de la terminación.")
        return redirect("admin_afiliado_detail", pk=pk)
    deactivate_afiliado(
        profile, motivo=form.cleaned_data["reason"], notas=form.cleaned_data["notes"],
        anular_comisiones=form.cleaned_data["void_commissions"], usuario=request.user,
    )
    messages.success(request, f"Se terminó la participación de {profile.user.email}. Se le avisó por correo.")
    return redirect("admin_afiliado_detail", pk=pk)


@require_perms("afiliados.change_perfilafiliado")
@require_POST
def afiliado_advance_exit(request, pk):
    """Hace efectiva de inmediato una baja que el propio afiliado solicito."""
    profile = get_object_or_404(PerfilAfiliado, pk=pk)
    if not profile.baja_solicitada:
        messages.error(request, "Este afiliado no tiene un aviso de baja.")
        return redirect("admin_afiliado_detail", pk=pk)
    deactivate_afiliado(profile, motivo=MotivoSalida.VOLUNTARY)
    messages.success(request, f"Se adelantó la baja de {profile.user.email}.")
    return redirect("admin_afiliado_detail", pk=pk)


@staff_required
def withdrawals_list(request):
    # "Comisiones de afiliados" se unifico dentro de "Afiliados" (ver
    # `afiliados_list`); esta ruta se conserva solo para no romper
    # enlaces viejos.
    return redirect("admin_afiliados")


@require_perms("afiliados.change_withdrawalrequest")
@require_POST
def withdrawal_resolve(request, pk):
    solicitud = get_object_or_404(WithdrawalRequest, pk=pk)
    aprobar = request.POST.get("action") == "pay"
    gastos = Decimal("0.00")
    if aprobar:
        try:
            gastos = Decimal(request.POST.get("transaction_fee", "").strip().replace(",", ".") or "0")
            resolve_withdrawal(solicitud, True, request.user, transaction_fee=gastos)
        except (InvalidOperation, ValueError):
            messages.error(request, "Los gastos de transacción deben ser un valor entre 0 y el monto de la solicitud.")
            return _safe_redirect(request, "admin_afiliados")
    else:
        resolve_withdrawal(solicitud, False, request.user)
    messages.success(
        request,
        "Solicitud de comisión pagada. Se le avisó al afiliado por correo." if aprobar else "Solicitud de comisión rechazada.",
    )
    return _safe_redirect(request, "admin_afiliados")


@require_perms("afiliados.delete_perfilafiliado")
@require_POST
def afiliado_delete(request, pk):
    profile = get_object_or_404(PerfilAfiliado, pk=pk)
    email = profile.user.email
    try:
        profile.delete()
    except ProtectedError:
        messages.error(
            request,
            f"No se puede eliminar al afiliado {email}: tiene comisiones o solicitudes de retiro "
            "registradas. Desactívalo o dalo de baja en lugar de eliminarlo.",
        )
        return redirect("admin_afiliados")
    messages.success(request, f"Afiliado {email} eliminado.")
    return redirect("admin_afiliados")


@require_perms("afiliados.change_perfilafiliado")
@require_POST
def afiliados_notify(request):
    """Aviso por correo a todos los afiliados activos (cambio de terminos o
    del programa)."""
    asunto = request.POST.get("subject", "").strip()[:150]
    mensaje = request.POST.get("message", "").strip()[:3000]
    if not asunto or not mensaje:
        messages.error(request, "Escribe el asunto y el mensaje del aviso.")
        return redirect("admin_afiliados")
    enviados = avisar_afiliados(asunto, mensaje)
    messages.success(request, f"Aviso enviado a {enviados} afiliado(s) activo(s).")
    return redirect("admin_afiliados")


@require_perms("afiliados.change_commission")
@require_POST
def commission_void(request, pk):
    comision = get_object_or_404(Commission.objects.select_related("afiliado"), pk=pk)
    try:
        anulada = anular_comision(comision, request.POST.get("reason", ""), request.user)
    except ValueError as error:
        messages.error(request, str(error))
    else:
        if anulada:
            messages.success(request, "Comisión anulada." if comision.status == CommissionStatus.REVERTED else "La comisión ya se había pagado: queda por recuperar y se descuenta del próximo pago.")
        else:
            messages.info(request, "Esa comisión ya no se puede anular.")
    return redirect("admin_afiliado_detail", pk=comision.afiliado_id)


@require_perms("afiliados.change_commission")
@require_POST
def commission_release(request, pk):
    comision = get_object_or_404(Commission, pk=pk)
    liberar_revision(comision, request.user, request.POST.get("note", "").strip())
    messages.success(request, "Revisión resuelta: la comisión sigue su curso.")
    return redirect("admin_afiliado_detail", pk=comision.afiliado_id)


@require_perms("afiliados.change_commission")
@require_POST
def commission_extend(request, pk):
    comision = get_object_or_404(Commission, pk=pk)
    try:
        hasta = datetime.strptime(request.POST.get("until", ""), "%Y-%m-%d").date()
        extender_validacion(comision, hasta, request.POST.get("reason", ""), request.user)
    except ValueError as error:
        mensaje = str(error)
        if "does not match" in mensaje or "unconverted" in mensaje:
            mensaje = "Escribe una fecha válida."
        messages.error(request, mensaje)
    else:
        messages.success(request, "Periodo de validación extendido. Se avisó al afiliado por correo.")
    return redirect("admin_afiliado_detail", pk=comision.afiliado_id)
