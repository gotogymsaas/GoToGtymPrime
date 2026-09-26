from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from influencer.models import InfluencerProfile
from inventory.models import Inventory
from orders.models import Coupon, Order, OrderStatus
from orders.services import (
    InvalidOrderTransitionError,
    apply_order_status_transition,
    valid_next_statuses,
)
from payments.models import PaymentTransaction
from products.models import (
    Brand,
    Product,
    ProductCategory,
    ProductMedia,
    ProductTag,
    ProductVariant,
)
from products.variant_parsing import COLOR_UNKNOWN, SIZE_UNKNOWN, build_sku
from tienda.catalog import SIZE_ORDER

from .forms import (
    BrandForm,
    CategoryForm,
    CouponForm,
    GroupForm,
    PanelSettingsForm,
    ProductAdminForm,
    ProductTagForm,
    ProductVariantFormSet,
)
from .models import PanelSettings
from .permissions import (
    grant_full_admin_permissions,
    require_perms,
    revoke_full_admin_permissions,
    staff_required,
)


@staff_required
def dashboard(request):
    User = get_user_model()
    panel_settings = PanelSettings.load()
    context = {
        "product_count": Product.objects.count(),
        "user_count": User.objects.count(),
        "influencer_count": InfluencerProfile.objects.filter(is_active=True).count(),
        "category_count": ProductCategory.objects.count(),
        "stock_total": Product.objects.aggregate(total=Sum("stock")).get("total") or 0,
        "low_stock_count": Inventory.objects.filter(
            quantity_available__gt=0, quantity_available__lte=panel_settings.low_stock_threshold,
        ).count(),
        "out_of_stock_count": Inventory.objects.filter(quantity_available=0).count(),
        "active_coupon_count": Coupon.objects.filter(is_active=True).count(),
        "latest_products": Product.objects.select_related("category", "brand").order_by("-id")[:10],
        "latest_users": User.objects.order_by("-id")[:10],
    }
    return render(request, "administracion/dashboard.html", context)


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
        .order_by("-id")
    )
    if query:
        products = products.filter(name__icontains=query)
    paginator = Paginator(products, 8)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "administracion/products.html", {"page_obj": page_obj, "query": query})


def _safe_redirect(request, fallback):
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


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
        if not form.cleaned_data.get("size") or not (form.cleaned_data.get("color") or "").strip():
            continue
        form.save_with_inventory(product)


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
                    _save_variant_formset(variant_formset, product)
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
        },
    )


@require_perms("products.change_product")
def product_media_delete(request, pk, media_id):
    media = get_object_or_404(ProductMedia, pk=media_id, product_id=pk)
    if request.method == "POST":
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
    if request.method == "POST":
        imagenes = request.FILES.getlist("image")
        if not imagenes:
            messages.error(request, "Selecciona al menos una imagen.")
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
    product.delete()
    messages.success(request, "Producto eliminado del catalogo comercial.")
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
        messages.error(request, "La cantidad de stock debe ser un numero entero valido (0 o mas).")
        return _safe_redirect(request, "admin_variants")

    Inventory.objects.update_or_create(variant=variant, defaults={"quantity_available": cantidad})
    messages.success(request, f"Stock de {variant.sku} actualizado a {cantidad}.")
    return _safe_redirect(request, "admin_variants")


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
    return _safe_redirect(request, "admin_variants")


@staff_required
def orders_list(request):
    """Pedidos y sus pagos viven en una sola pantalla: buscar por
    referencia de pago encuentra el pedido, y el detalle del pedido ya
    trae su historial completo de transacciones (ver order_detail.html).
    Antes existia ademas una pantalla "Pagos" separada que mostraba la
    misma tabla de transacciones sin nada que Pedidos no tuviera ya --
    solo duplicaba la informacion en dos lugares."""
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
    query = request.GET.get("q", "").strip()

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
def users_list(request):
    User = get_user_model()
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    users = User.objects.order_by("-id")
    if query:
        users = users.filter(
            Q(email__icontains=query)
            | Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    if role == "admin":
        users = users.filter(is_staff=True)
    elif role == "influencer":
        users = users.filter(is_staff=False, es_influencer=True)
    elif role == "user":
        users = users.filter(is_staff=False, es_influencer=False)
    elif role == "inactive":
        users = users.filter(is_active=False)
    paginator = Paginator(users, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "administracion/users.html",
        {
            "page_obj": page_obj,
            "query": query,
            "role": role,
            "all_groups": Group.objects.order_by("name"),
        },
    )


@require_perms("accounts.change_user")
@require_POST
def user_role_update(request, pk):
    """Cambia el rol (Usuario/Influencer/Administrador) de un usuario.

    is_staff y es_influencer son los flags ya existentes en el modelo; el
    rol es una combinacion de ambos, no un campo nuevo. Un admin no puede
    quitarse a si mismo el acceso administrativo desde aqui, para evitar
    quedar bloqueado fuera del panel sin otro administrador presente.
    """
    target = get_object_or_404(get_user_model(), pk=pk)
    nuevo_rol = request.POST.get("role", "")

    if target.pk == request.user.pk and nuevo_rol != "admin":
        messages.error(request, "No puedes quitarte a ti mismo el rol de administrador.")
        return _safe_redirect(request, "admin_users")

    if nuevo_rol == "admin":
        target.is_staff = True
        target.es_influencer = False
    elif nuevo_rol == "influencer":
        target.is_staff = False
        target.es_influencer = True
    elif nuevo_rol == "user":
        target.is_staff = False
        target.es_influencer = False
    else:
        messages.error(request, "Rol invalido.")
        return _safe_redirect(request, "admin_users")

    target.save(update_fields=["is_staff", "es_influencer"])

    # El paquete completo de permisos es lo que hace que "Administrador"
    # tenga acceso a todo sin depender de un Grupo armado a mano; al bajar
    # de rol se retira ese paquete, pero sin tocar permisos que el usuario
    # tenga por pertenecer a un Grupo (un rol intermedio no depende de
    # haber sido Administrador antes).
    if nuevo_rol == "admin":
        grant_full_admin_permissions(target)
    else:
        revoke_full_admin_permissions(target)

    messages.success(request, f"Rol de {target.email} actualizado.")
    return _safe_redirect(request, "admin_users")


@require_perms("accounts.change_user")
@require_POST
def user_toggle_active(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
        return _safe_redirect(request, "admin_users")

    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    estado = "activada" if target.is_active else "desactivada"
    messages.success(request, f"Cuenta de {target.email} {estado}.")
    return _safe_redirect(request, "admin_users")


@require_perms("accounts.delete_user")
@require_POST
def user_delete(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
        return _safe_redirect(request, "admin_users")
    if target.is_superuser:
        messages.error(request, "No se puede eliminar una cuenta de superusuario desde el panel.")
        return _safe_redirect(request, "admin_users")

    email = target.email
    target.delete()
    messages.success(request, f"Usuario {email} eliminado.")
    return _safe_redirect(request, "admin_users")


@require_perms("auth.add_group", "auth.change_group")
@require_POST
def user_groups_update(request, pk):
    """Asigna a un usuario los grupos (roles intermedios) marcados.

    Distinto de `user_role_update`: el rol basico (Usuario/Influencer/
    Administrador) sigue viviendo en `is_staff`/`es_influencer`, y esto
    es un permiso adicional, acotado, que solo tiene efecto si el usuario
    ya es staff (el panel completo sigue exigiendo `is_staff=True`; un
    Grupo nunca lo otorga por si solo).
    """
    target = get_object_or_404(get_user_model(), pk=pk)
    group_ids = request.POST.getlist("groups")
    target.groups.set(Group.objects.filter(pk__in=group_ids))
    messages.success(request, f"Grupos de {target.email} actualizados.")
    return _safe_redirect(request, "admin_users")


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
            messages.error(request, "No tienes permisos para esta accion.")
            return redirect("admin_catalogs")
        if kind == "category":
            category_form = CategoryForm(request.POST, prefix="category")
            if category_form.is_valid():
                category_form.save()
                messages.success(request, "Categoria creada.")
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
        messages.error(request, "No se puede eliminar la categoria porque tiene productos asociados.")
        return redirect("admin_catalogs")
    category.delete()
    messages.success(request, "Categoria eliminada.")
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
            messages.success(request, "Cupon guardado.")
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
    messages.success(request, f"Cupon {coupon.code} {estado}.")
    return redirect("admin_coupons")


@require_perms("orders.delete_coupon")
@require_POST
def coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.delete()
    messages.success(request, "Cupon eliminado.")
    return redirect("admin_coupons")


@staff_required
def groups_list(request):
    """Roles intermedios: Grupos de Django con un subconjunto de permisos
    del panel. Aparte de Usuario/Influencer/Administrador, un Grupo permite
    darle a alguien acceso solo a, por ejemplo, inventario y cupones."""
    groups = Group.objects.order_by("name").prefetch_related("permissions")
    return render(request, "administracion/groups.html", {"groups": groups})


@require_perms("auth.add_group", "auth.change_group")
def group_edit(request, pk=None):
    group = get_object_or_404(Group, pk=pk) if pk else None
    if request.method == "POST":
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, "Grupo guardado.")
            return redirect("admin_groups")
    else:
        form = GroupForm(instance=group)
    return render(request, "administracion/group_form.html", {"form": form, "group": group})


@require_perms("auth.delete_group")
@require_POST
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group.delete()
    messages.success(request, "Grupo eliminado.")
    return redirect("admin_groups")


