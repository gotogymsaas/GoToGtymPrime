import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from gotogym.ratelimit import rate_limit
from orders.models import Order
from orders.services import confirm_payment

from .models import PaymentTransaction
from .providers.mercadopago import MercadoPagoPaymentProvider
from .providers.mock import MockPaymentProvider
from .signature import verify_signature

# Proveedor usado por la pantalla de simulacion (Sprint 9): siempre el mock,
# sin importar PAYMENT_PROVIDER, porque esa pantalla existe precisamente
# para forzar estados de prueba y no tendria sentido con un proveedor real.
mock_provider = MockPaymentProvider()

_MENSAJES_SIMULACION = {
    PaymentTransaction.Status.PENDING: ('info', 'Pago marcado como pendiente (simulado).'),
    PaymentTransaction.Status.APPROVED: ('success', 'Pago aprobado (simulado).'),
    PaymentTransaction.Status.REJECTED: ('error', 'Pago rechazado (simulado).'),
    PaymentTransaction.Status.CANCELLED: ('warning', 'Pago cancelado (simulado).'),
}


def get_active_provider():
    """Proveedor que efectivamente abre el intento de pago del checkout.

    Configurable via `PAYMENT_PROVIDER`; en cualquier entorno que no lo
    declare explicitamente (todos, hoy) sigue siendo el simulado. Pasar a
    Mercado Pago real es cambiar esta variable, no tocar el checkout.
    """
    if getattr(settings, 'PAYMENT_PROVIDER', 'mock') == 'mercadopago':
        return MercadoPagoPaymentProvider()
    return mock_provider


def mock_ui_enabled():
    """La UI de simulacion solo se muestra en desarrollo (DEBUG) o si se
    activa explicitamente. Nunca debe quedar visible en produccion real."""
    return settings.DEBUG or getattr(settings, 'PAYMENTS_MOCK_UI_ENABLED', False)


def _latest_transaction(order, provider):
    return (
        PaymentTransaction.objects
        .filter(order=order, provider=provider.name)
        .order_by('-created_at')
        .first()
    )


def _current_or_new_transaction(order, provider):
    """Transaccion vigente sin crear una nueva solo por navegar a la pagina.

    Solo se crea un intento la primera vez que se visita (no hay ninguna
    transaccion todavia); en cualquier otra visita se muestra la que ya
    existe, sea cual sea su estado. Abrir un intento nuevo tras un rechazo
    es una accion explicita, no un efecto secundario de un GET.
    """
    return _latest_transaction(order, provider) or provider.create_payment_intent(order)


@login_required
def payment_pending(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    provider = get_active_provider()
    transaction = _current_or_new_transaction(order, provider)
    return render(request, 'payments/pending.html', {
        'order': order,
        'transaction': transaction,
        'mock_ui_enabled': mock_ui_enabled(),
        'estados': PaymentTransaction.Status.choices,
    })


@login_required
@require_POST
@rate_limit('payment_simulate', limit=20, period_seconds=60)
def simulate(request, order_number, status):
    if not mock_ui_enabled():
        raise Http404()

    valid_statuses = {choice for choice, _label in PaymentTransaction.Status.choices}
    if status not in valid_statuses:
        raise Http404()

    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    transaction = _current_or_new_transaction(order, mock_provider)
    mock_provider.force_status(transaction, status)

    if status == PaymentTransaction.Status.APPROVED:
        # El efecto de negocio (descontar stock, confirmar el pedido) se
        # dispara aqui mismo: en produccion lo haria el webhook real, pero
        # el punto de entrada al dominio es el mismo confirm_payment.
        confirm_payment(order, transaction)
    else:
        order.payment_status = status
        order.save(update_fields=['payment_status', 'updated_at'])

    nivel, texto = _MENSAJES_SIMULACION[status]
    getattr(messages, nivel)(request, texto)

    # El resultado de la simulacion ya quedo reflejado en el pedido (estado
    # de pago, y si aplica, orden confirmada); de ahi en adelante lo que
    # importa es el pedido, no la pantalla de pago.
    return redirect('orders:order_detail', order_number=order.order_number)


@csrf_exempt
@require_POST
def mercadopago_webhook(request):
    """Webhook de Mercado Pago: existe y valida origen, pero no hay ninguna
    integracion activa que lo invoque hoy (`PAYMENT_PROVIDER=mock` por
    defecto). Queda listo para cuando se activen credenciales reales.
    """
    secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', '')
    if not verify_signature(request, secret):
        return HttpResponseForbidden('Firma invalida o ausente.')

    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return HttpResponse(status=400)

    provider = MercadoPagoPaymentProvider()
    try:
        transaction = provider.handle_callback(payload)
    except PaymentTransaction.DoesNotExist:
        return HttpResponse(status=404)

    if transaction.status == PaymentTransaction.Status.APPROVED:
        confirm_payment(transaction.order, transaction)

    return HttpResponse(status=200)
