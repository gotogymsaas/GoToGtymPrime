"""Inventario del panel: stock por variante, ajuste masivo, historial y umbral."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from inventory.models import Inventory, InventoryAdjustment, InventoryAdjustmentReason
from inventory.services import record_adjustment
from products.models import (
    ProductCategory,
    ProductVariant,
)
from tienda.catalog import SIZE_ORDER

from ..forms import PanelSettingsForm
from ..models import PanelSettings
from ..permissions import (
    require_perms,
    staff_required,
)
from ._comun import _safe_redirect


@staff_required
def variants_list(request):
    """Inventario: stock por variante, con indicadores, filtros combinables
    (categoria/talla/color) y actualizacion rapida.

    Los filtros salen de los datos reales de variante (`size`, `color`) y
    de la categoria del producto (`product__category`), no de una lista
    fija: una talla o color que nadie usa todavia no aparece, y uno nuevo
    que se registre aparece solo, sin tocar esta vista.
    """
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    talla = request.GET.get("talla", "").strip()
    color = request.GET.get("color", "").strip()

    variants = (
        ProductVariant.objects
        .select_related("product", "product__category")
        .select_related("inventory")
        .order_by("product__name", "size", "color")
    )
    if query:
        variants = variants.filter(Q(sku__icontains=query) | Q(product__name__icontains=query))
    if categoria_id:
        variants = variants.filter(product__category_id=categoria_id)
    if talla:
        variants = variants.filter(size=talla)
    if color:
        variants = variants.filter(color=color)

    threshold = PanelSettings.load().low_stock_threshold
    if status == "out":
        variants = variants.filter(inventory__quantity_available=0)
    elif status == "low":
        variants = variants.filter(
            inventory__quantity_available__gt=0,
            inventory__quantity_available__lte=threshold,
        )

    paginator = Paginator(variants, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    tallas_disponibles = sorted(
        ProductVariant.objects.order_by().values_list("size", flat=True).distinct(),
        key=lambda talla: (SIZE_ORDER.index(talla) if talla in SIZE_ORDER else len(SIZE_ORDER), talla),
    )
    colores_disponibles = sorted(
        ProductVariant.objects.order_by().values_list("color", flat=True).distinct(),
    )

    return render(
        request,
        "administracion/variants.html",
        {
            "page_obj": page_obj,
            "query": query,
            "status": status,
            "low_stock_threshold": threshold,
            "threshold_form": PanelSettingsForm(instance=PanelSettings.load()),
            "categorias": ProductCategory.objects.order_by("name"),
            "tallas": tallas_disponibles,
            "colores": colores_disponibles,
            "selected_categoria": categoria_id,
            "selected_talla": talla,
            "selected_color": color,
        },
    )


@require_perms("inventory.change_inventory")
@require_POST
def variant_stock_update(request, pk):
    variant = get_object_or_404(ProductVariant, pk=pk)
    try:
        cantidad = int(request.POST.get("quantity_available", ""))
        if cantidad < 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "La cantidad de stock debe ser un número entero válido (0 o más).")
        return _safe_redirect(request, "admin_variants")

    anterior = Inventory.objects.filter(variant=variant).values_list("quantity_available", flat=True).first() or 0
    inventario, _ = Inventory.objects.update_or_create(variant=variant, defaults={"quantity_available": cantidad})
    if cantidad != anterior:
        record_adjustment(
            inventario, delta=cantidad - anterior, reason=InventoryAdjustmentReason.MANUAL,
            created_by=request.user,
        )
    messages.success(request, f"Stock de {variant.sku} actualizado a {cantidad}.")
    return _safe_redirect(request, "admin_variants")


# Valores que admite el ajuste masivo de Productos. Se acotan aqui para que
# los botones no se conviertan en un campo libre capaz de fijar cualquier
# cantidad a todo el catalogo con una sola peticion.
CANTIDADES_AJUSTE_MASIVO = (0, 5)


@require_perms("inventory.change_inventory")
@require_POST
def inventory_bulk_set(request):
    """Deja todas las variantes con la misma cantidad disponible.

    Cada variante que cambia deja su ajuste manual en el historial, igual
    que la edicion individual, para que el kardex siga explicando el stock.
    Las variantes sin fila de inventario reciben una, asi que tras el ajuste
    ninguna queda como "sin inventario"."""
    try:
        cantidad = int(request.POST.get("cantidad", ""))
    except (TypeError, ValueError):
        cantidad = None
    if cantidad not in CANTIDADES_AJUSTE_MASIVO:
        messages.error(request, "Ajuste masivo de inventario no válido.")
        return _safe_redirect(request, "admin_products")

    with transaction.atomic():
        Inventory.objects.bulk_create(
            [Inventory(variant=variante) for variante in ProductVariant.objects.filter(inventory__isnull=True)]
        )
        a_cambiar = [
            inventario
            for inventario in Inventory.objects.select_for_update().order_by("variant_id")
            if inventario.quantity_available != cantidad
        ]
        Inventory.objects.filter(pk__in=[inventario.pk for inventario in a_cambiar]).update(
            quantity_available=cantidad, updated_at=timezone.now(),
        )
        InventoryAdjustment.objects.bulk_create([
            InventoryAdjustment(
                inventory=inventario, delta=cantidad - inventario.quantity_available,
                quantity_after=cantidad, reason=InventoryAdjustmentReason.MANUAL,
                created_by=request.user,
            )
            for inventario in a_cambiar
        ])

    if cantidad == 0:
        messages.warning(request, f"Inventario llevado a 0: {len(a_cambiar)} variantes ajustadas.")
    else:
        messages.success(request, f"Inventario precargado con {cantidad} unidades: {len(a_cambiar)} variantes ajustadas.")
    return _safe_redirect(request, "admin_products")


@staff_required
def variant_inventory_history(request, pk):
    variant = get_object_or_404(ProductVariant.objects.select_related("product"), pk=pk)
    ajustes = InventoryAdjustment.objects.filter(inventory__variant=variant).select_related("created_by")
    return render(
        request,
        "administracion/variant_inventory_history.html",
        {"variant": variant, "ajustes": ajustes},
    )


@require_perms("administracion.change_panelsettings")
@require_POST
def inventory_threshold_update(request):
    """Umbral de "stock bajo": vive en Inventario, no en una pantalla de
    configuracion aparte, porque es lo unico que ese umbral afecta."""
    form = PanelSettingsForm(request.POST, instance=PanelSettings.load())
    if form.is_valid():
        form.save()
        messages.success(request, "Umbral de stock bajo actualizado.")
    else:
        for error in form.errors.values():
            messages.error(request, error.as_text())
    return _safe_redirect(request, "admin_dashboard")
