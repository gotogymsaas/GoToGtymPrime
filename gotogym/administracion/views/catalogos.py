"""Catalogos del panel: categorias, marcas y etiquetas."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from products.models import (
    Brand,
    ProductCategory,
    ProductTag,
)

from ..forms import (
    BrandForm,
    CategoryForm,
    ProductTagForm,
)
from ..permissions import (
    require_perms,
    staff_required,
)


@staff_required
def catalogs(request):
    category_form = CategoryForm(prefix="category")
    brand_form = BrandForm(prefix="brand")
    tag_form = ProductTagForm(prefix="tag")
    if request.method == "POST":
        kind = request.POST.get("kind")
        required_perm = {
            "category": "products.add_productcategory",
            "brand": "products.add_brand",
            "tag": "products.add_producttag",
        }.get(kind)
        if required_perm and not request.user.has_perm(required_perm):
            messages.error(request, "No tienes permisos para esta acción.")
            return redirect("admin_catalogs")
        if kind == "category":
            category_form = CategoryForm(request.POST, prefix="category")
            if category_form.is_valid():
                category_form.save()
                messages.success(request, "Categoría creada.")
                return redirect("admin_catalogs")
        if kind == "brand":
            brand_form = BrandForm(request.POST, prefix="brand")
            if brand_form.is_valid():
                brand_form.save()
                messages.success(request, "Marca creada.")
                return redirect("admin_catalogs")
        if kind == "tag":
            tag_form = ProductTagForm(request.POST, prefix="tag")
            if tag_form.is_valid():
                tag_form.save()
                messages.success(request, "Etiqueta creada.")
                return redirect("admin_catalogs")
    return render(
        request,
        "administracion/catalogs.html",
        {
            "category_form": category_form,
            "brand_form": brand_form,
            "tag_form": tag_form,
            "categories": ProductCategory.objects.order_by("name"),
            "brands": Brand.objects.order_by("name"),
            "tags": ProductTag.objects.order_by("name"),
        },
    )


@require_perms("products.change_producttag")
@require_POST
def tag_toggle(request, pk):
    tag = get_object_or_404(ProductTag, pk=pk)
    tag.is_active = not tag.is_active
    tag.save(update_fields=["is_active"])
    estado = "activada" if tag.is_active else "desactivada"
    messages.success(request, f"Etiqueta {tag.name} {estado}.")
    return redirect("admin_catalogs")


@require_perms("products.delete_producttag")
@require_POST
def tag_delete(request, pk):
    tag = get_object_or_404(ProductTag, pk=pk)
    tag.delete()
    messages.success(request, "Etiqueta eliminada.")
    return redirect("admin_catalogs")


@require_perms("products.delete_productcategory")
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(ProductCategory, pk=pk)
    if category.products.exists():
        messages.error(request, "No se puede eliminar la categoría porque tiene productos asociados.")
        return redirect("admin_catalogs")
    category.delete()
    messages.success(request, "Categoría eliminada.")
    return redirect("admin_catalogs")


@require_perms("products.delete_brand")
@require_POST
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if brand.products.exists():
        messages.error(request, "No se puede eliminar la marca porque tiene productos asociados.")
        return redirect("admin_catalogs")
    brand.delete()
    messages.success(request, "Marca eliminada.")
    return redirect("admin_catalogs")
