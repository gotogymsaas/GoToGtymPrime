"""Tarjetas de regalo del panel."""
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from gotogym.tasks import enqueue
from orders import correos as correos_de_pedidos
from orders import tarjetas_regalo
from orders.models import (
    GiftCard,
    GiftCardStatus,
)

from ..permissions import require_perms


@require_perms("orders.view_order")
def gift_cards_list(request):
    """Tarjetas de regalo vendidas, con lo que la tienda debe en saldo sin
    canjear (un pasivo, no un ingreso)."""
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    tarjetas = GiftCard.objects.select_related("purchase_order", "buyer").order_by("-created_at")
    ahora = timezone.now()
    if status == "active":
        tarjetas = tarjetas.filter(status=GiftCardStatus.ACTIVE, expires_at__gte=ahora)
    elif status == "expired":
        tarjetas = tarjetas.filter(status=GiftCardStatus.ACTIVE, expires_at__lt=ahora)
    elif status == "unsent":
        tarjetas = tarjetas.filter(status=GiftCardStatus.ACTIVE, sent_at__isnull=True)
    elif status in GiftCardStatus.values:
        tarjetas = tarjetas.filter(status=status)
    if query:
        codigo = tarjetas_regalo.normalizar_codigo(query)
        filtro = (
            Q(recipient_email__icontains=query)
            | Q(buyer__email__icontains=query)
            | Q(purchase_order__order_number__icontains=query)
        )
        if 4 <= len(codigo) <= tarjetas_regalo.LARGO_CODIGO:
            filtro |= Q(code__endswith=codigo)
        tarjetas = tarjetas.filter(filtro)

    vendidas = (
        GiftCard.objects.exclude(status__in=[GiftCardStatus.PENDING, GiftCardStatus.CANCELLED])
        .exclude(purchase_order__is_test_order=True)
    )
    resumen = {
        "saldo_vigente": tarjetas_regalo.saldo_vigente(),
        "vendido": vendidas.aggregate(total=Sum("initial_amount"))["total"] or Decimal("0"),
        "saldo_vencido": (
            GiftCard.objects.filter(status=GiftCardStatus.ACTIVE, expires_at__lt=ahora)
            .aggregate(total=Sum("balance"))["total"] or Decimal("0")
        ),
        "sin_enviar": GiftCard.objects.filter(status=GiftCardStatus.ACTIVE, sent_at__isnull=True).count(),
    }
    paginator = Paginator(tarjetas, 25)
    return render(
        request,
        "administracion/gift_cards.html",
        {
            "page_obj": paginator.get_page(request.GET.get("page")),
            "query": query,
            "status": status,
            "resumen": resumen,
            "ahora": ahora,
        },
    )


@require_perms("orders.view_order")
def gift_card_detail(request, pk):
    tarjeta = get_object_or_404(GiftCard.objects.select_related("purchase_order", "buyer"), pk=pk)
    return render(
        request,
        "administracion/gift_card_detail.html",
        {
            "tarjeta": tarjeta,
            "movimientos": tarjeta.movements.select_related("order", "created_by"),
            "ahora": timezone.now(),
        },
    )


@require_perms("orders.change_order")
@require_POST
def gift_card_toggle(request, pk):
    """Bloquea o desbloquea una tarjeta emitida. Bloquear no toca el saldo:
    solo impide canjearla mientras se resuelve un caso (fraude, reclamo)."""
    tarjeta = get_object_or_404(GiftCard, pk=pk)
    with transaction.atomic():
        if tarjeta.status == GiftCardStatus.ACTIVE:
            motivo = request.POST.get("reason", "").strip() or f"Bloqueada desde el panel por {request.user.email}."
            tarjetas_regalo.bloquear(tarjeta, motivo, request.user)
            messages.success(request, f"Tarjeta {tarjeta.masked_code} bloqueada.")
        elif tarjeta.status == GiftCardStatus.DISABLED:
            tarjetas_regalo.desbloquear(tarjeta)
            messages.success(request, f"Tarjeta {tarjeta.masked_code} desbloqueada.")
        else:
            messages.error(request, "Solo se puede bloquear o desbloquear una tarjeta emitida y sin anular.")
    return redirect("admin_gift_card_detail", pk=pk)


@require_perms("orders.change_order")
@require_POST
def gift_card_resend(request, pk):
    """Reenvia el correo de regalo, si hace falta a un correo corregido (el
    comprador escribio mal el del destinatario)."""
    tarjeta = get_object_or_404(GiftCard, pk=pk)
    if tarjeta.status not in (GiftCardStatus.ACTIVE, GiftCardStatus.DISABLED) or tarjeta.expires_at is None:
        messages.error(request, "Solo se reenvía una tarjeta emitida y sin anular.")
        return redirect("admin_gift_card_detail", pk=pk)
    nuevo_correo = request.POST.get("recipient_email", "").strip().lower()
    if nuevo_correo and nuevo_correo != tarjeta.recipient_email:
        try:
            validate_email(nuevo_correo)
        except ValidationError:
            messages.error(request, "El correo nuevo no es válido.")
            return redirect("admin_gift_card_detail", pk=pk)
        GiftCard.objects.filter(pk=tarjeta.pk).update(recipient_email=nuevo_correo, updated_at=timezone.now())
    enqueue(correos_de_pedidos.tarjeta_regalo_para_destinatario, tarjeta.pk)
    messages.success(request, "Correo de la tarjeta enviado de nuevo.")
    return redirect("admin_gift_card_detail", pk=pk)
