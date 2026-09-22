from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from influencer.models import InfluencerProfile
from orders.models import Order, OrderStatus
from orders.services import InvalidOrderTransitionError, apply_order_status_transition, valid_next_statuses
from payments.models import PaymentTransaction
from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant

from .forms import (
    BrandForm,
    CategoryForm,
    ProductAdminForm,
    ProductMediaForm,
    ProductVariantFormSet,
)


def staff_required(view_func):
    decorated = never_cache(login_required(user_passes_test(lambda user: user.is_staff)(view_func)))
    return decorated


@staff_required
def dashboard(request):
    User = get_user_model()
    context = {
        "product_count": Product.objects.count(),
        "user_count": User.objects.count(),
        "influencer_count": InfluencerProfile.objects.filter(is_active=True).count(),
        "category_count": ProductCategory.objects.count(),
        "stock_total": Product.objects.aggregate(total=Sum("stock")).get("total") or 0,
        "latest_products": Product.objects.select_related("category", "brand").order_by("-id")[:10],
        "latest_users": User.objects.order_by("-id")[:10],
    }
    return render(request, "administracion/dashboard.html", context)


@staff_required
def products_list(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.select_related("category", "brand").order_by("-id")
    if query:
        products = products.filter(name__icontains=query)
    paginator = Paginator(products, 8)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "administracion/products.html", {"page_obj": page_obj, "query": query})


def _save_variant_formset(formset, product):
    """Aplica el formset de variantes sobre `product`.

    Una variante marcada para eliminar solo se borra de verdad si nunca
    aparecio en un pedido; si ya tiene `OrderItem` asociados, se desactiva
    (`is_active=False`) en su lugar para no romper el historico de ventas.
    """
    for form in formset.forms:
        if not form.cleaned_data:
            continue
        if form.cleaned_data.get("DELETE"):
            variant = form.instance
            if variant.pk and variant.order_items.exists():
                variant.is_active = False
                variant.save(update_fields=["is_active"])
            elif variant.pk:
                variant.delete()
            continue
        if not form.cleaned_data.get("sku"):
            continue
        form.save_with_inventory(product)


@staff_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    variant_formset = None

    if request.method == "POST":
        form = ProductAdminForm(request.POST, request.FILES, instance=product)
        if product is not None:
            variant_formset = ProductVariantFormSet(request.POST, instance=product)

        formset_ok = variant_formset is None or variant_formset.is_valid()
        if form.is_valid() and formset_ok:
            if product and request.POST.get("clear_image") == "1" and product.image:
                product.image.delete(save=False)
                product.image = None
            product = form.save()
            if variant_formset is not None:
                _save_variant_formset(variant_formset, product)
            messages.success(request, "Producto guardado. La tienda comercial ya lee este cambio.")
            return redirect("admin_product_edit", pk=product.pk)
    else:
        form = ProductAdminForm(instance=product)
        if product is not None:
            variant_formset = ProductVariantFormSet(instance=product)

    return render(
        request,
        "administracion/product_form.html",
        {
            "form": form,
            "product": product,
            "variant_formset": variant_formset,
            "media_form": ProductMediaForm() if product else None,
            "media_items": product.media.all() if product else None,
        },
    )


@staff_required
def product_media_delete(request, pk, media_id):
    media = get_object_or_404(ProductMedia, pk=media_id, product_id=pk)
    if request.method == "POST":
        if media.image:
            media.image.delete(save=False)
        media.delete()
        messages.success(request, "Imagen eliminada.")
    return redirect("admin_product_edit", pk=pk)


@staff_required
def product_media_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductMediaForm(request.POST, request.FILES)
        if form.is_valid():
            media = form.save(commit=False)
            media.product = product
            media.save()
            if media.is_primary:
                ProductMedia.objects.filter(product=product).exclude(pk=media.pk).update(is_primary=False)
            messages.success(request, "Imagen agregada.")
        else:
            for error in form.errors.values():
                messages.error(request, error.as_text())
    return redirect("admin_product_edit", pk=pk)


@staff_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.success(request, "Producto eliminado del catalogo comercial.")
    return redirect("admin_products")


@staff_required
@require_POST
def product_image_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.image:
        product.image.delete(save=False)
        product.image = None
        product.save(update_fields=["image"])
        messages.success(request, "Imagen eliminada.")
    return redirect("admin_product_edit", pk=pk)


@staff_required
def variants_list(request):
    """Listado de solo lectura de las variantes del catalogo, con su stock."""
    query = request.GET.get("q", "").strip()
    variants = (
        ProductVariant.objects
        .select_related("product")
        .select_related("inventory")
        .order_by("product__name", "size", "color")
    )
    if query:
        variants = variants.filter(Q(sku__icontains=query) | Q(product__name__icontains=query))
    paginator = Paginator(variants, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "administracion/variants.html", {"page_obj": page_obj, "query": query})


@staff_required
def orders_list(request):
    orders = Order.objects.select_related("address").order_by("-created_at")

    order_status = request.GET.get("order_status", "").strip()
    payment_status = request.GET.get("payment_status", "").strip()
    query = request.GET.get("q", "").strip()

    if order_status:
        orders = orders.filter(order_status=order_status)
    if payment_status:
        orders = orders.filter(payment_status=payment_status)
    if query:
        orders = orders.filter(Q(order_number__icontains=query) | Q(email__icontains=query))

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
            "order_status_choices": Order._meta.get_field("order_status").choices,
            "payment_status_choices": Order._meta.get_field("payment_status").choices,
        },
    )


@staff_required
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects
        .select_related("address", "shipping_quote")
        .prefetch_related("items", "payment_transactions"),
        order_number=order_number,
    )
    etiquetas = dict(OrderStatus.choices)
    siguientes = [(estado, etiquetas.get(estado, estado)) for estado in valid_next_statuses(order)]

    return render(
        request,
        "administracion/order_detail.html",
        {
            "order": order,
            "next_statuses": siguientes,
        },
    )


@staff_required
@require_POST
def order_update_status(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    nuevo_estado = request.POST.get("order_status", "")

    # payment_status nunca se acepta desde este formulario: lo controla
    # exclusivamente el proveedor de pago via confirm_payment. Si alguien
    # manipulara el POST para incluirlo, se ignora en silencio (no se lee
    # en ningun momento de aqui en adelante).
    try:
        apply_order_status_transition(order, nuevo_estado)
    except InvalidOrderTransitionError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Estado del pedido actualizado.")
    return redirect("admin_order_detail", order_number=order_number)


@staff_required
def payment_transactions_list(request):
    """Listado de solo lectura de transacciones de pago, para trazabilidad."""
    query = request.GET.get("q", "").strip()
    transactions = PaymentTransaction.objects.select_related("order").order_by("-created_at")
    if query:
        transactions = transactions.filter(
            Q(order__order_number__icontains=query)
            | Q(preference_id__icontains=query)
            | Q(payment_id__icontains=query)
        )
    paginator = Paginator(transactions, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "administracion/payment_transactions.html", {"page_obj": page_obj, "query": query})


@staff_required
def users_list(request):
    User = get_user_model()
    query = request.GET.get("q", "").strip()
    users = User.objects.order_by("-id")
    if query:
        users = users.filter(
            Q(email__icontains=query)
            | Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    paginator = Paginator(users, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "administracion/users.html", {"page_obj": page_obj, "query": query})


@staff_required
def catalogs(request):
    category_form = CategoryForm(prefix="category")
    brand_form = BrandForm(prefix="brand")
    if request.method == "POST":
        if request.POST.get("kind") == "category":
            category_form = CategoryForm(request.POST, prefix="category")
            if category_form.is_valid():
                category_form.save()
                messages.success(request, "Categoria creada.")
                return redirect("admin_catalogs")
        if request.POST.get("kind") == "brand":
            brand_form = BrandForm(request.POST, prefix="brand")
            if brand_form.is_valid():
                brand_form.save()
                messages.success(request, "Marca creada.")
                return redirect("admin_catalogs")
    return render(
        request,
        "administracion/catalogs.html",
        {
            "category_form": category_form,
            "brand_form": brand_form,
            "categories": ProductCategory.objects.order_by("name"),
            "brands": Brand.objects.order_by("name"),
        },
    )


@staff_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(ProductCategory, pk=pk)
    if category.products.exists():
        messages.error(request, "No se puede eliminar la categoria porque tiene productos asociados.")
        return redirect("admin_catalogs")
    category.delete()
    messages.success(request, "Categoria eliminada.")
    return redirect("admin_catalogs")


@staff_required
@require_POST
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if brand.products.exists():
        messages.error(request, "No se puede eliminar la marca porque tiene productos asociados.")
        return redirect("admin_catalogs")
    brand.delete()
    messages.success(request, "Marca eliminada.")
    return redirect("admin_catalogs")
