from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import Brand, Product, ProductCategory

from .forms import BrandForm, CategoryForm, ProductAdminForm


def staff_required(view_func):
    decorated = login_required(user_passes_test(lambda user: user.is_staff)(view_func))
    return decorated


@staff_required
def dashboard(request):
    User = get_user_model()
    context = {
        "product_count": Product.objects.count(),
        "user_count": User.objects.count(),
        "category_count": ProductCategory.objects.count(),
        "stock_total": Product.objects.aggregate(total=Sum("stock")).get("total") or 0,
        "latest_products": Product.objects.select_related("category", "brand").order_by("-id")[:5],
        "latest_users": User.objects.order_by("-date_joined")[:5],
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


@staff_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    if request.method == "POST":
        form = ProductAdminForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            if product and request.POST.get("clear_image") == "1" and product.image:
                product.image.delete(save=False)
                product.image = None
            form.save()
            messages.success(request, "Producto guardado. La tienda comercial ya lee este cambio.")
            return redirect("admin_products")
    else:
        form = ProductAdminForm(instance=product)
    return render(request, "administracion/product_form.html", {"form": form, "product": product})


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
def users_list(request):
    User = get_user_model()
    query = request.GET.get("q", "").strip()
    users = User.objects.order_by("-date_joined")
    if query:
        users = users.filter(email__icontains=query)
    paginator = Paginator(users, 12)
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
