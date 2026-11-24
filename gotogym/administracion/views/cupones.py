"""Cupones del panel."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from orders.models import Coupon

from ..forms import CouponForm
from ..permissions import (
    require_perms,
    staff_required,
)


@staff_required
def coupons_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    coupons = Coupon.objects.order_by("-created_at")
    if query:
        coupons = coupons.filter(code__icontains=query.upper())
    if status == "active":
        coupons = coupons.filter(is_active=True)
    elif status == "inactive":
        coupons = coupons.filter(is_active=False)

    paginator = Paginator(coupons, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "administracion/coupons.html",
        {"page_obj": page_obj, "query": query, "status": status},
    )


@require_perms("orders.add_coupon", "orders.change_coupon")
def coupon_edit(request, pk=None):
    coupon = get_object_or_404(Coupon, pk=pk) if pk else None
    if request.method == "POST":
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, "Cupón guardado.")
            return redirect("admin_coupons")
    else:
        form = CouponForm(instance=coupon)
    return render(request, "administracion/coupon_form.html", {"form": form, "coupon": coupon})


@require_perms("orders.change_coupon")
@require_POST
def coupon_toggle(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.is_active = not coupon.is_active
    coupon.save(update_fields=["is_active"])
    estado = "activado" if coupon.is_active else "desactivado"
    messages.success(request, f"Cupón {coupon.code} {estado}.")
    return redirect("admin_coupons")


@require_perms("orders.delete_coupon")
@require_POST
def coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.delete()
    messages.success(request, "Cupón eliminado.")
    return redirect("admin_coupons")
