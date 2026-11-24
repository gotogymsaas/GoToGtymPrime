"""Ciclo de vida del afiliado: aprobacion, rechazo, baja con preaviso,
aceptacion de terminos y seguimiento de su actividad.

Las funciones que avanzan el tiempo (`aplicar_bajas_vencidas`) son
idempotentes y se invocan tambien al abrir los paneles, ademas de existir
como comando de gestion.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from gotogym.tasks import enqueue
from orders.models import Coupon, CouponDiscountType

from .. import correos, terminos
from ..models import (
    CommissionStatus,
    ConfiguracionProgramaAfiliados,
    EstadoAfiliado,
    MotivoSalida,
    PerfilAfiliado,
)
from .comisiones import _anular, recompute_profile_totals

# Dias de calendario entre el aviso de baja y su efecto.
DIAS_DE_PREAVISO = 15


def _ensure_personal_coupon(profile):
    """Genera (o reactiva) el cupon personal del afiliado: el mismo codigo
    que ve en su panel (`referral_code`) queda utilizable en el checkout."""
    existente = profile.coupons.first()
    if existente is not None:
        update_fields = []
        if not existente.is_active:
            existente.is_active = True
            update_fields.append('is_active')
        # El afiliado puede proponer un codigo distinto cada vez que vuelve
        # a postularse (ver `afiliados.views.suscribete`); si el cupon ya
        # existia con el codigo anterior, queda desincronizado del panel y
        # del listado de Cupones hasta que se actualiza aqui tambien.
        if existente.code != profile.referral_code:
            existente.code = profile.referral_code
            update_fields.append('code')
        if update_fields:
            existente.save(update_fields=update_fields)
        return existente

    settings_obj = ConfiguracionProgramaAfiliados.load()
    return Coupon.objects.create(
        code=profile.referral_code,
        discount_type=CouponDiscountType.PERCENTAGE,
        value=settings_obj.default_customer_discount,
        afiliado=profile,
        is_active=True,
    )


def _limpiar_salida(profile):
    profile.exit_requested_at = None
    profile.exit_effective_at = None
    profile.exited_at = None
    profile.exit_reason = ''
    profile.exit_notes = ''


@transaction.atomic
def approve_afiliado(profile, reviewer):
    """Aprueba (o reactiva) a un afiliado: activa su rol, genera su cupon
    personal si no existe y deja constancia de quien y cuando lo reviso."""
    profile.status = EstadoAfiliado.APPROVED
    profile.is_active = True
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewer
    profile.rejection_reason = ''
    _limpiar_salida(profile)
    profile.save(update_fields=[
        'status', 'is_active', 'reviewed_at', 'reviewed_by', 'rejection_reason',
        'exit_requested_at', 'exit_effective_at', 'exited_at', 'exit_reason', 'exit_notes',
    ])

    profile.user.es_afiliado = True
    profile.user.save(update_fields=['es_afiliado'])

    _ensure_personal_coupon(profile)
    enqueue(correos.afiliado_aprobado, profile.pk)
    return profile


def reject_afiliado(profile, reviewer, motivo=''):
    profile.status = EstadoAfiliado.REJECTED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewer
    profile.rejection_reason = (motivo or '').strip()[:500]
    profile.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'rejection_reason'])
    enqueue(correos.afiliado_rechazado, profile.pk)
    return profile


def deactivate_afiliado(profile, motivo='', notas='', anular_comisiones=False, usuario=None):
    """Baja del programa: usada por el afiliado al cancelar su solicitud, por
    el vencimiento de su preaviso y por un administrador. No borra nada --
    conserva el historico de pedidos y comisiones -- solo desactiva el acceso
    y el cupon. Las comisiones que ya tiene siguen su curso y se le pagan.

    `motivo` es un `MotivoSalida`. Sin motivo, una baja con preaviso queda
    como voluntaria. Si se da de baja a quien aun era aprobado, se le avisa.
    `anular_comisiones` invalida las que aun no se han pagado (fraude)."""
    era_aprobado = profile.status == EstadoAfiliado.APPROVED and profile.is_active
    if not motivo and profile.exit_requested_at:
        motivo = MotivoSalida.VOLUNTARY
    profile.is_active = False
    profile.exited_at = timezone.now()
    profile.exit_reason = motivo
    profile.exit_notes = (notas or '').strip()
    profile.save(update_fields=['is_active', 'exited_at', 'exit_reason', 'exit_notes'])
    profile.coupons.update(is_active=False)
    profile.user.es_afiliado = False
    profile.user.save(update_fields=['es_afiliado'])

    if anular_comisiones:
        texto = f'Anulada por la terminación del afiliado: {profile.exit_notes or profile.get_exit_reason_display()}'
        for comision in profile.commissions.filter(
            status__in=(CommissionStatus.PENDING, CommissionStatus.APPROVED),
        ).select_related('withdrawal_request'):
            _anular(comision, texto, usuario)
    recompute_profile_totals(profile)

    if era_aprobado:
        if motivo == MotivoSalida.VOLUNTARY:
            enqueue(correos.baja_efectiva, profile.pk)
        elif motivo:
            enqueue(correos.terminacion, profile.pk)


def solicitar_baja(profile, ahora=None):
    """Registra el aviso de baja del afiliado: se hace efectiva tras el
    preaviso y, mientras tanto, su codigo y su panel siguen activos."""
    if not profile.is_active or profile.exit_requested_at:
        return profile
    ahora = ahora or timezone.now()
    profile.exit_requested_at = ahora
    profile.exit_effective_at = ahora + timedelta(days=DIAS_DE_PREAVISO)
    profile.save(update_fields=['exit_requested_at', 'exit_effective_at'])
    enqueue(correos.baja_solicitada, profile.pk)
    return profile


def cancelar_baja(profile):
    profile.exit_requested_at = None
    profile.exit_effective_at = None
    profile.save(update_fields=['exit_requested_at', 'exit_effective_at'])
    return profile


def aplicar_bajas_vencidas(ahora=None):
    """Da de baja a quien ya cumplio su preaviso. Devuelve cuantos."""
    ahora = ahora or timezone.now()
    vencidos = list(PerfilAfiliado.objects.filter(is_active=True, exit_effective_at__lte=ahora))
    for perfil in vencidos:
        deactivate_afiliado(perfil, motivo=MotivoSalida.VOLUNTARY)
    return len(vencidos)


def afiliado_operativo(profile, ahora=None):
    """Si el codigo del afiliado todavia debe aceptarse: esta activo y su
    preaviso de baja, si lo hay, no ha vencido (aunque la baja aun no se haya
    aplicado en la base)."""
    return profile.es_operativo(ahora)


def necesita_reaceptar_terminos(profile):
    """Los afiliados activos deben haber aceptado la version vigente."""
    return (
        profile.status == EstadoAfiliado.APPROVED
        and profile.is_active
        and profile.terms_version != terminos.VERSION_TERMINOS_AFILIADOS
    )


def aceptar_terminos_vigentes(profile):
    profile.terms_version = terminos.VERSION_TERMINOS_AFILIADOS
    profile.terms_accepted_at = timezone.now()
    profile.save(update_fields=['terms_version', 'terms_accepted_at'])


# --- Actividad ----------------------------------------------------------------

def ultima_actividad(profile):
    """Ultimo clic o ultima venta del afiliado; si no tiene ninguno, cuando
    fue aprobado o se postulo."""
    ultimo_clic = profile.referral_clicks.aggregate(m=Max('created_at'))['m']
    ultima_venta = profile.referred_orders.aggregate(m=Max('created_at'))['m']
    fechas = [f for f in (ultimo_clic, ultima_venta) if f]
    return max(fechas) if fechas else (profile.reviewed_at or profile.created_at)


def afiliados_inactivos(dias=None, ahora=None):
    """Afiliados activos sin clics ni ventas hace `dias` dias o mas, con su
    ultima actividad. No se da de baja a nadie automaticamente."""
    ahora = ahora or timezone.now()
    dias = dias if dias is not None else ConfiguracionProgramaAfiliados.load().inactivity_days
    limite = ahora - timedelta(days=dias)
    perfiles = (
        PerfilAfiliado.objects.filter(status=EstadoAfiliado.APPROVED, is_active=True)
        .select_related('user')
    )
    resultado = []
    for perfil in perfiles:
        ultima = ultima_actividad(perfil)
        if ultima < limite:
            resultado.append((perfil, ultima))
    return resultado
