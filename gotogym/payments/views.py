import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from gotogym.ajustes_tienda import MENSAJE_PAGOS_DESHABILITADOS, pagos_habilitados
from gotogym.ratelimit import rate_limit
from integrations.mercadopago.mercadopago_client import MercadoPagoError
from orders.models import Order
from orders.services import confirm_payment

from .models import PaymentTransaction
from .providers.mercadopago import MercadoPagoPaymentProvider
from .providers.mock import MockPaymentProvider
from .signature import verify_signature

logger = logging.getLogger(__name__)

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
    if not pagos_habilitados():
        # Con los pagos deshabilitados no se abre ningun intento nuevo; si el
        # pedido ya estaba pagado, la pantalla se muestra igual.
        previa = _latest_transaction(order, provider)
        if previa is None or previa.status != PaymentTransaction.Status.APPROVED:
            messages.warning(request, str(MENSAJE_PAGOS_DESHABILITADOS))
            return redirect('orders:order_detail', order_number=order.order_number)
    try:
        transaction = _current_or_new_transaction(order, provider)
    except MercadoPagoError:
        logger.exception('No se pudo crear la preferencia de pago de %s', order.order_number)
        messages.error(request, gettext(
            'No pudimos conectar con Mercado Pago. Intenta de nuevo en unos minutos.'
        ))
        return redirect('orders:order_detail', order_number=order.order_number)

    checkout_url = ''
    if provider.name == 'mercadopago' and transaction.status != PaymentTransaction.Status.APPROVED:
        checkout_url = provider.checkout_url(transaction)

    return render(request, 'payments/pending.html', {
        'order': order,
        'transaction': transaction,
        'checkout_url': checkout_url,
        # La simulacion usa su propio proveedor: con uno real activo no
        # tiene nada que ver con el pago que se esta mostrando.
        'mock_ui_enabled': mock_ui_enabled() and provider.name == 'mock',
        'estados': PaymentTransaction.Status.choices,
    })


@login_required
def payment_return(request, order_number):
    """Adonde vuelve el comprador desde Mercado Pago (back_urls).

    Los parametros de la URL (`payment_id`, `status`...) los puede escribir
    cualquiera, asi que solo se usa el id para consultar el pago a Mercado
    Pago. Sin esto, el pedido dependeria de que el webhook llegue (y en
    local, donde Mercado Pago no puede llamar, nunca llegaria).
    """
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    payment_id = request.GET.get('payment_id') or request.GET.get('collection_id') or ''

    if payment_id.isdigit() and getattr(settings, 'PAYMENT_PROVIDER', 'mock') == 'mercadopago':
        try:
            transaction = MercadoPagoPaymentProvider().sync_payment(payment_id)
        except (PaymentTransaction.DoesNotExist, MercadoPagoError):
            logger.exception('No se pudo verificar el pago %s del pedido %s', payment_id, order.order_number)
        else:
            if transaction.order_id == order.pk:
                if transaction.status == PaymentTransaction.Status.APPROVED:
                    confirm_payment(order, transaction)
                    messages.success(request, gettext('¡Pago recibido! Tu pedido quedó confirmado.'))
                    return redirect('orders:order_detail', order_number=order.order_number)
                if transaction.status == PaymentTransaction.Status.PENDING:
                    messages.info(request, gettext(
                        'Tu pago está en proceso. Te avisaremos cuando Mercado Pago lo confirme.'
                    ))
                else:
                    messages.error(request, gettext('El pago no fue aprobado. Puedes intentarlo de nuevo.'))

    return redirect('payments:pending', order_number=order.order_number)


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
    """Webhook de Mercado Pago: valida la firma, y del aviso solo toma el id
    del pago, cuyo estado se consulta a la API (ver `sync_payment`)."""
    secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', '')
    if not verify_signature(request, secret):
        return HttpResponseForbidden('Firma inválida o ausente.')

    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return HttpResponse(status=400)

    # Mercado Pago tambien avisa de otros temas (merchant_order, etc.) si se
    # suscriben en el panel: se acusa recibo para que no los reintente.
    tipo = payload.get('type') or request.GET.get('type') or 'payment'
    if tipo != 'payment':
        return HttpResponse(status=200)

    # El id de la query es el que cubre la firma; el del cuerpo no.
    payment_id = request.GET.get('data.id') or (payload.get('data') or {}).get('id')
    provider = MercadoPagoPaymentProvider()
    try:
        transaction = provider.handle_callback({'data': {'id': payment_id}})
    except PaymentTransaction.DoesNotExist:
        return HttpResponse(status=404)
    except MercadoPagoError:
        logger.exception('Webhook: no se pudo consultar el pago %s', payment_id)
        # 5xx para que Mercado Pago reintente: no es culpa del aviso.
        return HttpResponse(status=502)

    if transaction.status == PaymentTransaction.Status.APPROVED:
        confirm_payment(transaction.order, transaction)

    return HttpResponse(status=200)
