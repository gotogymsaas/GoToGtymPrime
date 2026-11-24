"""Productos del panel: listado, edicion con variantes, galeria e imagenes."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from inventory.models import Inventory
from orders.models import OrderItem
from products.models import (
    Product,
    ProductMedia,
    ProductVariant,
)
from products.variant_parsing import COLOR_UNKNOWN, SIZE_UNKNOWN, build_sku
from tienda.catalog import ORDEN_DEL_PANEL

from ..forms import (
    PanelSettingsForm,
    ProductAdminForm,
    ProductVariantFormSet,
    validar_imagen,
)
from ..models import PanelSettings
from ..permissions import (
    require_perms,
    staff_required,
)


@staff_required
def products_list(request):
    """Listado de productos, con el stock real (suma de Inventory de sus
    variantes) en vez del campo heredado `Product.stock`: ese campo no lo
    lee Inventario ni el checkout, asi que mostrarlo aqui como si fuera el
    stock vigente es lo que hacia parecer que un producto con unidades
    "disponibles" en este listado no tuviera ninguna en Inventario."""
    query = request.GET.get("q", "").strip()
    products = (
        Product.objects
        .select_related("category", "brand")
        .prefetch_related("tags", "media")
        .annotate(
            variant_count=Count("variants", distinct=True),
            real_stock=Sum("variants__inventory__quantity_available"),
        )
        .order_by(*ORDEN_DEL_PANEL)
    )
    if query:
        products = products.filter(name__icontains=query)
    context = {
        "products": products,
        "query": query,
        # Sin paginar, para que todo el orden este a la vista y se pueda
        # arrastrar cualquier producto a cualquier posicion. Con una busqueda
        # activa solo se ve un subconjunto, asi que ahi no se reordena.
        "puede_reordenar": request.user.has_perm("products.change_product") and not query,
        "threshold_form": PanelSettingsForm(instance=PanelSettings.load()),
    }
    return render(request, "administracion/products.html", context)


@require_perms("products.change_product")
@require_POST
def products_reorder(request):
    """Guarda el orden del catalogo tras arrastrar y soltar una fila.

    Recibe los ids (`product_id`, repetido) en el orden final. Los ids
    recibidos se reparten, en ese orden, entre los huecos que ya ocupaban en
    el catalogo, y despues se renumera todo de 1 a N: asi un subconjunto no
    mueve a los demas, un id desconocido se ignora y los empates o huecos
    heredados de datos viejos no dejan el orden ambiguo."""
    recibidos = []
    for crudo in request.POST.getlist("product_id"):
        try:
            recibidos.append(int(crudo))
        except ValueError:
            continue

    with transaction.atomic():
        orden = list(
            Product.objects.select_for_update().only("pk", "sort_order").order_by(*ORDEN_DEL_PANEL)
        )
        por_id = {producto.pk: producto for producto in orden}
        enviados = [por_id[pk] for pk in dict.fromkeys(recibidos) if pk in por_id]
        if not enviados:
            return JsonResponse({"ok": False}, status=400)

        ids_enviados = {producto.pk for producto in enviados}
        huecos = [i for i, producto in enumerate(orden) if producto.pk in ids_enviados]
        for hueco, producto in zip(huecos, enviados, strict=True):
            orden[hueco] = producto

        cambiados = []
        for posicion, producto in enumerate(orden, start=1):
            if producto.sort_order != posicion:
                producto.sort_order = posicion
                cambiados.append(producto)
        Product.objects.bulk_update(cambiados, ["sort_order"])
    return JsonResponse({"ok": True})


def _save_variant_formset(formset, product, user=None):
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
        if not form.cleaned_data.get("size") or not (form.cleaned_data.get("color") or "").strip():
            continue
        form.save_with_inventory(product, user=user)


def _ensure_default_variant(product):
    """Si el producto se guarda sin ninguna variante, le crea una
    generica (talla UNICA, color UNICO) con el stock que el admin ya puso
    en el campo heredado `stock` del formulario principal.

    Inventario administra unidades por variante, no por producto: un
    producto sin ninguna variante no tenia forma de aparecer ahi ni de
    que se le gestionaran cantidades, aunque el admin ya hubiera puesto
    un numero de stock al crearlo. Esto cierra esa brecha sin exigirle al
    admin que entienda la distincion producto/variante para el caso mas
    simple (un producto con una sola presentacion).
    """
    if product.variants.exists():
        return
    sku = build_sku(product.pk, SIZE_UNKNOWN, COLOR_UNKNOWN)
    variante = ProductVariant.objects.create(
        product=product, sku=sku, size=SIZE_UNKNOWN, color=COLOR_UNKNOWN,
    )
    Inventory.objects.create(variant=variante, quantity_available=product.stock)


@require_perms("products.add_product", "products.change_product")
def product_edit(request, pk=None):
    """Crea o edita un producto junto con sus variantes (talla/color/stock)
    en el mismo formulario.

    Antes, un producto nuevo solo mostraba la tabla de variantes despues de
    guardarlo una primera vez (necesitaba su pk para el formset), lo que
    dejaba productos recien creados sin ninguna variante ni Inventory --
    y por lo tanto invisibles en el listado de Inventario. Ahora, al crear,
    el producto se guarda primero (dentro de la misma transaccion) y el
    formset de variantes se valida y guarda contra esa instancia ya
    persistida, sin necesidad de un segundo viaje al servidor.

    Si el POST no trae datos del formset (management form ausente), se
    guarda solo el producto: es el envio de un formulario que nunca
    mostro la tabla de variantes (por ejemplo, una integracion externa que
    solo conoce los campos del producto), no un error de validacion.
    """
    product = get_object_or_404(Product, pk=pk) if pk else None
    formset_prefix = ProductVariantFormSet.get_default_prefix()

    if request.method == "POST":
        form = ProductAdminForm(request.POST, request.FILES, instance=product)
        trae_variantes = f"{formset_prefix}-TOTAL_FORMS" in request.POST

        if form.is_valid():
            with transaction.atomic():
                product = form.save()

                if not trae_variantes:
                    _ensure_default_variant(product)
                    messages.success(request, "Producto guardado. La tienda comercial ya lee este cambio.")
                    return redirect("admin_product_edit", pk=product.pk)

                variant_formset = ProductVariantFormSet(request.POST, instance=product)
                if variant_formset.is_valid():
                    _save_variant_formset(variant_formset, product, user=request.user)
                    _ensure_default_variant(product)
                    messages.success(request, "Producto guardado. La tienda comercial ya lee este cambio.")
                    return redirect("admin_product_edit", pk=product.pk)
                # El producto ya quedo guardado (creado o editado); solo las
                # variantes tienen errores. Se re-muestra la pagina, ahora ya
                # en modo "editar" porque el producto existe de verdad.
        else:
            variant_formset = (
                ProductVariantFormSet(request.POST, instance=product)
                if product and trae_variantes
                else ProductVariantFormSet(instance=product or Product())
            )
    else:
        form = ProductAdminForm(instance=product)
        variant_formset = ProductVariantFormSet(instance=product or Product())

    return render(
        request,
        "administracion/product_form.html",
        {
            "form": form,
            "product": product,
            "variant_formset": variant_formset,
            "media_items": product.media.all() if product else None,
            "low_stock_threshold": PanelSettings.load().low_stock_threshold,
        },
    )


@require_perms("products.change_product")
@require_POST
def product_media_delete(request, pk, media_id):
    media = get_object_or_404(ProductMedia, pk=media_id, product_id=pk)
    if media.image:
        media.image.delete(save=False)
    media.delete()
    messages.success(request, "Imagen eliminada.")
    return redirect("admin_product_edit", pk=pk)


@require_perms("products.change_product")
@require_POST
def product_media_reorder(request, pk):
    """Persiste el nuevo orden de la galeria tras arrastrar y soltar.

    Recibe la lista completa de ids en el orden final (`media_id`,
    repetido); cualquier id que no pertenezca a este producto se ignora,
    para que no se pueda reordenar (ni de paso tocar) la galeria de otro
    producto manipulando el POST.
    """
    ids_en_orden = request.POST.getlist("media_id")
    medios_del_producto = {
        str(media.pk): media for media in ProductMedia.objects.filter(product_id=pk)
    }
    for posicion, media_id in enumerate(ids_en_orden):
        media = medios_del_producto.get(str(media_id))
        if media is not None:
            ProductMedia.objects.filter(pk=media.pk).update(sort_order=posicion)
    return JsonResponse({"ok": True})


@require_perms("products.change_product")
@require_POST
def product_media_add(request, pk):
    """Agrega una o varias imagenes a la galeria en una sola operacion.

    Sin alt_text/orden/"principal" a pedirle al admin: las nuevas fotos se
    agregan al final de las que ya existen (siguiendo el mayor
    `sort_order` actual), y cual se ve como principal ya lo resuelve
    `Product.primary_image` solo -- la primera por orden, salvo que alguna
    tenga `is_primary` explicito de antes. Arrastrar una foto a la primera
    posicion en la galeria (ver `admin_product_media_reorder`) ya es la
    forma de elegir cual es la principal; pedirlo tambien aqui con una
    casilla aparte era la misma decision expresada dos veces.
    """
    product = get_object_or_404(Product, pk=pk)
    imagenes = request.FILES.getlist("image")
    errores = []
    for imagen in imagenes:
        try:
            validar_imagen(imagen)
        except ValidationError as error:
            errores.extend(error.messages)
    if not imagenes:
        messages.error(request, "Selecciona al menos una imagen.")
    elif errores:
        # Si una falla no se sube ninguna: asi no queda la galeria a medias.
        for mensaje in errores:
            messages.error(request, mensaje)
    else:
        ultimo_orden = product.media.aggregate(maximo=Max("sort_order"))["maximo"]
        orden_base = 0 if ultimo_orden is None else ultimo_orden + 1
        for indice, imagen in enumerate(imagenes):
            ProductMedia.objects.create(
                product=product,
                image=imagen,
                sort_order=orden_base + indice,
            )
        messages.success(request, f"{len(imagenes)} imagen(es) agregada(s).")
    return redirect("admin_product_edit", pk=pk)


@require_perms("products.delete_product")
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    # Un producto que ya se vendio no se borra: sus variantes desaparecerian
    # de los pedidos (quedan sin enlace), los pedidos pagados en curso se
    # cancelarian al confirmar y se perderia el kardex. Se retira del catalogo.
    if OrderItem.objects.filter(variant__product=product).exists():
        product.variants.update(is_active=False)
        messages.warning(
            request,
            "El producto ya tiene ventas: no se elimina, se desactivaron sus variantes y dejo de mostrarse en la tienda.",
        )
        return redirect("admin_products")
    product.delete()
    messages.success(request, "Producto eliminado del catálogo comercial.")
    return redirect("admin_products")


@require_perms("products.change_product")
@require_POST
def product_image_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.image:
        product.image.delete(save=False)
        product.image = None
        product.save(update_fields=["image"])
        messages.success(request, "Imagen eliminada.")
    return redirect("admin_product_edit", pk=pk)
