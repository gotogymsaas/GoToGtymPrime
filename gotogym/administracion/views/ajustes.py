"""Interruptores y metas de la barra superior del panel."""
import logging

import sentry_sdk
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from gotogym import ajustes_tienda

from ..forms import SalesGoalForm
from ..models import PanelSettings
from ..permissions import require_perms
from ._comun import _safe_redirect

logger = logging.getLogger(__name__)


@require_perms("administracion.change_panelsettings")
@require_POST
def coach_toggle(request):
    """Interruptor "Habilitar Coach" (barra superior del panel).

    Decide si la tienda muestra Quantum Coach (la IA de GoToGym). No toca el
    carrito, el checkout ni el stock. Apagarlo oculta el boton y la ruta del
    Coach responde 404 desde el siguiente mensaje."""
    habilitar = request.POST.get("habilitar") == "1"
    ajustes = PanelSettings.load()
    if ajustes.coach_enabled != habilitar:
        ajustes.coach_enabled = habilitar
        ajustes.save(update_fields=["coach_enabled", "updated_at"])
    if not habilitar:
        messages.warning(request, "Coach deshabilitado: Quantum Coach ya no se muestra en la tienda.")
    elif not (settings.COACH_API_URL or settings.VENDEDOR_COACH_SIMULADO):
        messages.warning(
            request,
            "Coach habilitado, pero este entorno no tiene el servicio de IA configurado (COACH_API_URL): "
            "Quantum Coach se mostrará y responderá que la IA no está disponible por ahora.",
        )
    else:
        messages.success(request, "Coach habilitado: Quantum Coach se muestra en la tienda.")
    return _safe_redirect(request, "admin_dashboard")


def _avisar_modo_sin_pago_encendido(usuario):
    """Avisa a Sentry de que se encendio el modo de pruebas en un entorno real.
    Solo lleva el id de la cuenta (nada de correo ni datos personales). Un fallo
    del aviso no debe impedir encender el modo ni ocultar el resultado."""
    if settings.DEBUG:
        return
    try:
        with sentry_sdk.new_scope() as scope:
            scope.set_user({"id": str(usuario.pk)})
            sentry_sdk.capture_message(
                "Modo de pruebas 'Confirmar sin pagar (equipo)' encendido en un entorno real", level="warning",
            )
    except Exception:
        logger.exception("No se pudo avisar a Sentry del modo de pruebas.")


@require_perms("administracion.change_panelsettings")
@require_POST
def staff_checkout_without_payment_toggle(request):
    """Interruptor "Confirmar sin pagar (equipo)" (barra superior del panel).

    Modo de pruebas: mientras esta encendido, las cuentas del equipo
    confirman sus pedidos y tarjetas de regalo al pasar el checkout, sin ir a
    la pasarela. Los clientes siguen pagando. Esos pedidos quedan marcados
    como prueba (ver `orders.services.confirmar_sin_pago`)."""
    activar = request.POST.get("activar") == "1"
    if activar and not request.user.has_perm("administracion.toggle_test_mode"):
        # Apagarlo basta con `change_panelsettings`; encenderlo, que abre una
        # via de confirmar pedidos sin cobrar, exige un permiso propio.
        request.datos_de_bitacora = {"activar": "1", "resultado": "sin_permiso"}
        messages.error(request, "No tienes permiso para encender el modo de pruebas.")
        return _safe_redirect(request, "admin_dashboard")
    ajustes = PanelSettings.load()
    # El modo vencido sigue marcado en la base: encenderlo de nuevo renueva el plazo.
    if ajustes.staff_checkout_without_payment != activar or activar != ajustes_tienda.modo_sin_pago_activo():
        ajustes.staff_checkout_without_payment = activar
        ajustes.staff_checkout_without_payment_since = timezone.now() if activar else None
        ajustes.save(update_fields=["staff_checkout_without_payment", "updated_at"])
        if activar:
            _avisar_modo_sin_pago_encendido(request.user)
    request.datos_de_bitacora = {"activar": "1" if activar else "0"}
    if activar:
        messages.warning(
            request,
            "Modo de pruebas encendido: las cuentas del equipo confirman pedidos sin pagar. "
            "Se apaga solo a las 24 horas; apágalo antes al terminar de probar.",
        )
    else:
        messages.success(request, "Modo de pruebas apagado: todos los pedidos vuelven a requerir pago.")
    return _safe_redirect(request, "admin_dashboard")


@require_perms("administracion.change_panelsettings")
@require_POST
def online_payments_toggle(request):
    """Interruptor "Recibir pagos" (barra superior del panel).

    Solo decide si el checkout abre pagos nuevos con Mercado Pago. No toca
    pedidos ni stock, y un pago que ya estaba en curso (retorno del comprador
    o webhook) se sigue confirmando."""
    habilitar = request.POST.get("habilitar") == "1"
    ajustes = PanelSettings.load()
    if ajustes.online_payments_enabled != habilitar:
        ajustes.online_payments_enabled = habilitar
        ajustes.save(update_fields=["online_payments_enabled", "updated_at"])
    if habilitar:
        messages.success(request, "Pagos habilitados: el checkout vuelve a ofrecer Mercado Pago.")
    else:
        messages.warning(request, "Pagos deshabilitados: no se abren pagos nuevos. Los pagos en curso se siguen confirmando.")
    return _safe_redirect(request, "admin_dashboard")


@require_perms("administracion.change_panelsettings")
@require_POST
def sales_goal_update(request):
    """Meta de ventas customizable: reusa el mismo patron de ajuste rapido
    que el umbral de stock bajo, pero vive junto a los KPIs de ventas en el
    dashboard en vez de en Productos."""
    form = SalesGoalForm(request.POST, instance=PanelSettings.load())
    if form.is_valid():
        form.save()
        messages.success(request, "Meta de ventas actualizada.")
    else:
        for error in form.errors.values():
            messages.error(request, error.as_text())
    return _safe_redirect(request, "admin_dashboard")
