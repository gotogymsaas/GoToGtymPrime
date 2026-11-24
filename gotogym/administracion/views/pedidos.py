"""Pedidos del panel: listado, detalle, estado, guia y reembolso."""
from datetime import timedelta

from afiliados.services import revert_order_commission
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from orders.models import (
    Order,
    OrderKind,
    OrderStatus,
)
from orders.services import (
    InvalidOrderTransitionError,
    apply_order_status_transition,
    cancel_expired_orders,
    set_tracking_code,
    valid_next_statuses,
)
from payments.models import PaymentTransaction, Refund
from payments.services import RefundError, refund_order_payment

from ..permissions import require_perms

# Dias sin entregar tras el envio a partir de los cuales un pedido se lista
# como demorado.
DIAS_DE_ENVIO_DEMORADO = 10


@require_perms("orders.view_order")
def orders_list(request):
    """Pedidos y sus pagos viven en una sola pantalla: buscar por
    referencia de pago encuentra el pedido, y el detalle del pedido ya
    trae su historial completo de transacciones (ver order_detail.html).
    Antes existia ademas una pantalla "Pagos" separada que mostraba la
    misma tabla de transacciones sin nada que Pedidos no tuviera ya --
    solo duplicaba la informacion en dos lugares."""
    cancel_expired_orders()
    orders = (
        Order.objects
        .select_related("address")
        .prefetch_related(
            Prefetch("payment_transactions", queryset=PaymentTransaction.objects.order_by("-created_at")),
        )
        .order_by("-created_at")
    )

    order_status = request.GET.get("order_status", "").strip()
    payment_status = request.GET.get("payment_status", "").strip()
    kind = request.GET.get("kind", "").strip()
    query = request.GET.get("q", "").strip()
    if kind in OrderKind.values:
        orders = orders.filter(kind=kind)

    demorados = request.GET.get("demorados") == "1"
    if demorados:
        # Enviados y sin entregar hace tiempo: mientras no se marquen como
        # entregados no empieza el periodo de validacion de la comision del
        # afiliado, asi que conviene verlos aparte.
        limite = timezone.now() - timedelta(days=DIAS_DE_ENVIO_DEMORADO)
        orders = orders.filter(
            order_status__in=[OrderStatus.SHIPPED, OrderStatus.IN_TRANSIT], updated_at__lte=limite,
        )
    if order_status:
        orders = orders.filter(order_status=order_status)
    if payment_status:
        orders = orders.filter(payment_status=payment_status)
    if query:
        orders = orders.filter(
            Q(order_number__icontains=query)
            | Q(email__icontains=query)
            | Q(payment_transactions__preference_id__icontains=query)
            | Q(payment_transactions__payment_id__icontains=query)
        ).distinct()

    paginator = Paginator(orders, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "administracion/orders.html",
        {
            "page_obj": page_obj,
            "query": query,
            "order_status": order_status,
            "payment_status": payment_status,
            "kind": kind,
            "demorados": demorados,
            "dias_de_envio_demorado": DIAS_DE_ENVIO_DEMORADO,
            "order_status_choices": Order._meta.get_field("order_status").choices,
            "payment_status_choices": Order._meta.get_field("payment_status").choices,
        },
    )


@require_perms("orders.view_order")
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects
        .select_related("address", "shipping_quote", "referred_by__user", "gift_card", "purchased_gift_card")
        .prefetch_related("items", "payment_transactions"),
        order_number=order_number,
    )
    etiquetas = dict(OrderStatus.choices)
    siguientes = [(estado, etiquetas.get(estado, estado)) for estado in valid_next_statuses(order)]

    transaccion_aprobada = (
        order.payment_transactions.filter(status=PaymentTransaction.Status.APPROVED)
        .order_by("-created_at").first()
    )
    puede_reembolsar = (
        transaccion_aprobada is not None
        and order.order_status in (OrderStatus.CANCELLED, OrderStatus.RETURNED)
        and not transaccion_aprobada.refunds.filter(status=Refund.Status.APPROVED).exists()
    )

    return render(
        request,
        "administracion/order_detail.html",
        {
            "order": order,
            "next_statuses": siguientes,
            "puede_reembolsar": puede_reembolsar,
            "puede_editar_guia": hasattr(order, "shipping_quote") and order.order_status in (
                OrderStatus.SHIPPED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED),
            "refunds": Refund.objects.filter(payment_transaction__order=order).select_related("requested_by"),
            "history": order.status_history.select_related("changed_by"),
            "tarjeta_comprada": getattr(order, "purchased_gift_card", None) if order.is_gift_card_purchase else None,
        },
    )


@require_perms("orders.change_order")
@require_POST
def order_update_status(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    nuevo_estado = request.POST.get("order_status", "")

    # payment_status nunca se acepta desde este formulario: lo controla
    # exclusivamente el proveedor de pago via confirm_payment. Si alguien
    # manipulara el POST para incluirlo, se ignora en silencio (no se lee
    # en ningun momento de aqui en adelante).
    try:
        apply_order_status_transition(
            order, nuevo_estado,
            tracking_code=request.POST.get("tracking_code", ""), changed_by=request.user,
        )
    except InvalidOrderTransitionError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Estado del pedido actualizado.")
    return redirect("admin_order_detail", order_number=order_number)


@require_perms("orders.change_order")
@require_POST
def order_update_tracking(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    if order.order_status not in (OrderStatus.SHIPPED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED):
        messages.error(request, "La guía se registra cuando el pedido ya salió.")
    elif set_tracking_code(order, request.POST.get("tracking_code", "")):
        messages.success(request, "Guía de envío actualizada.")
    else:
        messages.error(request, "Este pedido no tiene cotización de envío donde guardar la guía.")
    return redirect("admin_order_detail", order_number=order_number)


@require_perms("payments.add_refund")
@require_POST
def order_refund(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    try:
        refund_order_payment(order, request.user)
    except RefundError as error:
        messages.error(request, str(error))
    else:
        # Un pedido reembolsado no genera comision: se anula, o se deja por
        # recuperar si ya se le habia pagado al afiliado.
        revert_order_commission(order, "El pedido fue reembolsado.")
        messages.success(request, "Reembolso procesado.")
    return redirect("admin_order_detail", order_number=order_number)
