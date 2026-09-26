from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from products.models import Product, ProductCategory, ProductMedia, ProductVariant

from .catalog import (
    LOW_STOCK_THRESHOLD,
    available_filter_values,
    build_product_card,
    build_variant_matrix,
    catalog_variants_queryset,
    color_swatch,
    primary_image,
    product_features,
    size_guide_rows,
    variant_stock,
)

PRODUCTS_PER_PAGE = 12

ORDER_OPTIONS = {
    'precio_asc': 'base_price',
    'precio_desc': '-base_price',
    'nombre_asc': 'name',
    'nombre_desc': '-name',
}


def _catalog_queryset():
    return (
        Product.objects
        .select_related('category', 'brand')
        .prefetch_related(
            Prefetch('variants', queryset=catalog_variants_queryset()),
            Prefetch('media', queryset=ProductMedia.objects.order_by('-is_primary', 'sort_order', 'id')),
        )
    )


@login_required
def producto_list(request):
    productos = _catalog_queryset()

    filtro = request.GET.get('filtro', '').strip()
    categoria_id = request.GET.get('categoria', '').strip()
    talla = request.GET.get('talla', '').strip()
    color = request.GET.get('color', '').strip()
    precio_min = request.GET.get('precio_min', '').strip()
    precio_max = request.GET.get('precio_max', '').strip()
    orden = request.GET.get('orden', '').strip()

    if filtro:
        productos = productos.filter(name__icontains=filtro)
    if categoria_id:
        productos = productos.filter(category_id=categoria_id)
    # Talla y color filtran por disponibilidad real: solo cuentan las variantes
    # activas que ademas tienen unidades en inventario.
    if talla:
        productos = productos.filter(
            variants__is_active=True,
            variants__size=talla,
            variants__inventory__quantity_available__gt=0,
        )
    if color:
        productos = productos.filter(
            variants__is_active=True,
            variants__color=color,
            variants__inventory__quantity_available__gt=0,
        )
    if talla or color:
        productos = productos.distinct()
    if precio_min:
        productos = productos.filter(base_price__gte=precio_min)
    if precio_max:
        productos = productos.filter(base_price__lte=precio_max)

    productos = productos.order_by(ORDER_OPTIONS.get(orden, 'id'))

    paginator = Paginator(productos, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    sizes, colors = available_filter_values()

    filtros_activos = any([filtro, categoria_id, talla, color, precio_min, precio_max])

    context = {
        'page_obj': page_obj,
        'cards': [build_product_card(producto) for producto in page_obj],
        'categorias': ProductCategory.objects.all().order_by('name'),
        'sizes': sizes,
        'colors': colors,
        'filtro': filtro,
        'selected_category_id': categoria_id,
        'selected_size': talla,
        'selected_color': color,
        'precio_min': precio_min,
        'precio_max': precio_max,
        'orden': orden,
        'filtros_activos': filtros_activos,
        'total_resultados': paginator.count,
    }
    return render(request, 'tienda/producto_list.html', context)


def _unique_preserving_order(values):
    vistos = []
    for value in values:
        if value not in vistos:
            vistos.append(value)
    return vistos


@login_required
def producto_detail(request, pk):
    producto = get_object_or_404(_catalog_queryset(), pk=pk)

    variantes = build_variant_matrix(producto)
    disponibles = [v for v in variantes if v['available']]
    precios = [v['price'] for v in variantes] or [producto.base_price]

    colores = _unique_preserving_order([v['color'] for v in variantes])
    reviews = list(producto.reviews.select_related('user').order_by('-created_at'))
    review_summary = producto.reviews.aggregate(average=Avg('rating'), count=Count('id'))

    related_products = (
        _catalog_queryset()
        .filter(category=producto.category)
        .exclude(pk=producto.pk)[:4]
    )

    context = {
        'producto': producto,
        'gallery': list(producto.media.all()) or None,
        'image': primary_image(producto),
        'variantes': variantes,
        'variantes_json': [
            {
                'id': v['id'],
                'sku': v['sku'],
                'size': v['size'],
                'color': v['color'],
                'price': float(v['price']),
                'available': v['available'],
                'stock': v['stock'],
            }
            for v in variantes
        ],
        'sizes': _unique_preserving_order([v['size'] for v in variantes]),
        'colors': [{'name': c, 'swatch': color_swatch(c)} for c in colores],
        'in_stock': bool(disponibles),
        'price_min': min(precios),
        'price_max': max(precios),
        'has_price_range': min(precios) != max(precios),
        # Con una sola variante no tiene sentido pedirle al usuario que elija:
        # se preselecciona y los selectores no se muestran.
        'single_variant': variantes[0] if len(variantes) == 1 else None,
        'related_cards': [build_product_card(p) for p in related_products],
        'low_stock_threshold': LOW_STOCK_THRESHOLD,
        'size_guide_rows': size_guide_rows(_unique_preserving_order([v['size'] for v in variantes])),
        'features': product_features(producto),
        'reviews': reviews,
        'review_average': review_summary['average'],
        'review_count': review_summary['count'],
    }
    return render(request, 'tienda/producto_detail.html', context)


@login_required
def producto_variante(request, pk):
    """Consulta de una combinacion talla/color concreta.

    Responde 404 si esa combinacion no existe para el producto, de modo que
    el cliente no pueda inventar variantes.
    """
    producto = get_object_or_404(Product, pk=pk)
    variante = get_object_or_404(
        ProductVariant.objects.select_related('inventory'),
        product=producto,
        size=request.GET.get('size', ''),
        color=request.GET.get('color', ''),
        is_active=True,
    )
    stock = variant_stock(variante)
    return JsonResponse({
        'variant_id': variante.id,
        'sku': variante.sku,
        'size': variante.size,
        'color': variante.color,
        'price': float(variante.effective_price),
        'available': stock > 0,
        'stock': stock,
    })
