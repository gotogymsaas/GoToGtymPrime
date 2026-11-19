from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext, gettext_lazy
from django.views.decorators.http import require_POST
from gotogym.ratelimit import rate_limit
from gotogym.seo import contexto_seo, recortar, url_absoluta
from products import linea
from products.models import Product, ProductCategory, ProductMedia, ProductVariant

from .catalog import (
    LOW_STOCK_THRESHOLD,
    ORDEN_DEL_PANEL,
    available_filter_values,
    build_product_card,
    build_variant_matrix,
    catalog_variants_queryset,
    color_swatch,
    product_features,
    product_gallery,
    size_guide_rows,
    storefront_products,
    variant_stock,
)
from .favoritos import fijar_favorito, ids_favoritos, tarjetas_favoritas, tarjetas_relacionadas

PRODUCTS_PER_PAGE = 12

# Opciones del filtro de linea. Unisex no es una opcion propia: esas prendas
# aparecen al elegir cualquiera de las dos.
LINEAS_DEL_FILTRO = {
    linea.DAMA: gettext_lazy('Dama'),
    linea.CABALLERO: gettext_lazy('Caballero'),
}

ORDER_OPTIONS = {
    'precio_asc': 'base_price',
    'precio_desc': '-base_price',
    'nombre_asc': 'name',
    'nombre_desc': '-name',
}


def _catalog_queryset():
    return (
        storefront_products()
        .select_related('category', 'brand')
        .prefetch_related(
            Prefetch('variants', queryset=catalog_variants_queryset()),
            Prefetch('media', queryset=ProductMedia.objects.order_by('-is_primary', 'sort_order', 'id')),
        )
    )


def producto_list(request):
    productos = _catalog_queryset()

    filtro = request.GET.get('filtro', '').strip()
    linea_elegida = request.GET.get('linea', '').strip()
    if linea_elegida not in LINEAS_DEL_FILTRO:
        linea_elegida = ''
    categoria_id = request.GET.get('categoria', '').strip()
    talla = request.GET.get('talla', '').strip()
    color = request.GET.get('color', '').strip()
    precio_min = request.GET.get('precio_min', '').strip()
    precio_max = request.GET.get('precio_max', '').strip()
    orden = request.GET.get('orden', '').strip()

    if filtro:
        productos = productos.filter(name__icontains=filtro)
    # Una prenda unisex sirve a las dos lineas, asi que aparece en ambas.
    if linea_elegida:
        productos = productos.filter(line__in=linea.lineas_compatibles(linea_elegida))
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

    if orden in ORDER_OPTIONS:
        productos = productos.order_by(ORDER_OPTIONS[orden])
    else:
        productos = productos.order_by(*ORDEN_DEL_PANEL)

    paginator = Paginator(productos, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    sizes, colors = available_filter_values()

    filtros_activos = any([filtro, linea_elegida, categoria_id, talla, color, precio_min, precio_max])
    lineas = [(valor, LINEAS_DEL_FILTRO[valor]) for valor in LINEAS_DEL_FILTRO]

    categorias = ProductCategory.objects.all().order_by('name')
    selected_category_name = ''
    if categoria_id:
        selected_category_name = next(
            (cat.name for cat in categorias if str(cat.id) == categoria_id), ''
        )

    context = {
        'page_obj': page_obj,
        'cards': [build_product_card(producto) for producto in page_obj],
        'categorias': categorias,
        'lineas': lineas,
        'selected_line': linea_elegida,
        'selected_line_name': LINEAS_DEL_FILTRO.get(linea_elegida, ''),
        'sizes': sizes,
        'colors': colors,
        'filtro': filtro,
        'selected_category_id': categoria_id,
        'selected_category_name': selected_category_name,
        'selected_size': talla,
        'selected_color': color,
        'precio_min': precio_min,
        'precio_max': precio_max,
        'orden': orden,
        'filtros_activos': filtros_activos,
        'total_resultados': paginator.count,
        'favoritos_ids': ids_favoritos(request.user),
    }
    context.update(contexto_seo(
        gettext('Tienda GoToGym: ropa deportiva'),
        gettext('Explora la colección de ropa deportiva GoToGym con tecnología textil: tallas, colores y precios.'),
    ))
    return render(request, 'tienda/producto_list.html', context)


def _unique_preserving_order(values):
    vistos = []
    for value in values:
        if value not in vistos:
            vistos.append(value)
    return vistos


def producto_detail(request, pk):
    producto = get_object_or_404(_catalog_queryset(), pk=pk)

    variantes = build_variant_matrix(producto)
    disponibles = [v for v in variantes if v['available']]
    # Variante que la ficha deja elegida al entrar: la de menor precio entre
    # las disponibles (o entre todas, si ninguna lo esta). A igual precio
    # gana la primera en el orden talla/color.
    candidatas = disponibles or variantes
    por_defecto = min(candidatas, key=lambda v: v['price']) if candidatas else None
    precio_inicial = por_defecto['price'] if por_defecto else producto.base_price

    colores = _unique_preserving_order([v['color'] for v in variantes])
    reviews = list(producto.reviews.select_related('user').order_by('-created_at'))
    review_summary = producto.reviews.aggregate(average=Avg('rating'), count=Count('id'))

    related_products = (
        _catalog_queryset()
        .filter(category=producto.category)
        .exclude(pk=producto.pk)
        .order_by(*ORDEN_DEL_PANEL)[:4]
    )

    context = {
        'producto': producto,
        'gallery': product_gallery(producto),
        'variantes': variantes,
        'variantes_json': [
            {
                'id': v['id'],
                'sku': v['sku'],
                'size': v['size'],
                'color': v['color'],
                'price': float(v['price']),
                'list_price': float(v['list_price']),
                'has_discount': v['has_discount'],
                'discount_percent': v['discount_percent'],
                'available': v['available'],
                'stock': v['stock'],
            }
            for v in variantes
        ],
        'sizes': _unique_preserving_order([v['size'] for v in variantes]),
        'colors': [{'name': c, 'swatch': color_swatch(c)} for c in colores],
        'in_stock': bool(disponibles),
        'default_variant': por_defecto,
        'price_min': precio_inicial,
        'price_max': precio_inicial,
        'has_price_range': False,
        'compare_price': por_defecto['list_price'] if por_defecto and por_defecto['has_discount'] else None,
        'discount_percent': por_defecto['discount_percent'] if por_defecto and por_defecto['has_discount'] else 0,
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
        'favoritos_ids': ids_favoritos(request.user),
    }
    context.update(_seo_de_producto(request, producto, variantes, context))
    return render(request, 'tienda/producto_detail.html', context)


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
        'list_price': float(variante.list_price),
        'has_discount': variante.has_discount,
        'discount_percent': variante.discount_percent,
        'available': stock > 0,
        'stock': stock,
    })


@login_required
def mis_favoritos(request):
    """Pagina de favoritos: lo guardado y, debajo, un carrusel de
    recomendaciones de las mismas categorias."""
    favoritos_cards = tarjetas_favoritas(request.user)
    context = {
        'favoritos_cards': favoritos_cards,
        'relacionados_cards': tarjetas_relacionadas(favoritos_cards),
        # Un solo conjunto para todos los corazones de la pagina: los de la
        # lista salen llenos y los del carrusel, vacios.
        'favoritos_ids': frozenset(card['product'].pk for card in favoritos_cards),
    }
    context.update(contexto_seo(
        gettext('Mis favoritos | GoToGym'),
        gettext('Los productos que guardaste en la tienda GoToGym.'),
    ))
    return render(request, 'tienda/favoritos.html', context)


def _destino_seguro(request, fallback):
    """Pagina desde la que se pulso el corazon, si es de este sitio."""
    destino = request.POST.get('next', '')
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return destino
    return fallback


@require_POST
@rate_limit('favoritos', limit=60, period_seconds=60)
def favorito(request, pk):
    """Agrega o quita un producto de favoritos.

    El formulario envia el estado deseado (`favorito=1` o `0`), no una orden
    de alternar. Con JavaScript responde JSON y la pagina no se recarga; sin
    JavaScript vuelve a la pagina de origen.

    Sin sesion no se guarda nada: se lleva al login y, al volver, la persona
    queda en la misma pagina para pulsar el corazon de nuevo.
    """
    quiere_json = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    producto = get_object_or_404(storefront_products(), pk=pk)
    volver_a = _destino_seguro(request, resolve_url('tienda:producto_detail', pk=producto.pk))

    if not request.user.is_authenticated:
        login_url = f"{resolve_url(settings.LOGIN_URL)}?{urlencode({'next': volver_a})}"
        if quiere_json:
            return JsonResponse({'ok': False, 'login_url': login_url}, status=401)
        return redirect(login_url)

    queda_favorito = fijar_favorito(request.user, producto, request.POST.get('favorito') == '1')
    if quiere_json:
        return JsonResponse({'ok': True, 'favorito': queda_favorito})
    return redirect(volver_a)


def _pesos(valor):
    """Pesos colombianos sin decimales: "100000", no "100000.0000"."""
    return str(int(round(valor)))


def _seo_de_producto(request, producto, variantes, context):
    """Metadatos y datos estructurados (schema.org/Product) de la ficha."""
    galeria = context['gallery']
    imagenes = [url_absoluta(request, foto.image.url) for foto in galeria if getattr(foto, 'image', None)]
    precios = [v['price'] for v in variantes] or [producto.base_price]
    disponibilidad = 'InStock' if context['in_stock'] else 'OutOfStock'
    base_oferta = {
        'priceCurrency': 'COP',
        'availability': f'https://schema.org/{disponibilidad}',
        'url': request.build_absolute_uri(request.path),
    }
    if min(precios) == max(precios):
        oferta = {'@type': 'Offer', 'price': _pesos(min(precios)), **base_oferta}
    else:
        oferta = {
            '@type': 'AggregateOffer', 'lowPrice': _pesos(min(precios)), 'highPrice': _pesos(max(precios)),
            'offerCount': len(variantes), **base_oferta,
        }
    datos = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': producto.name,
        'description': recortar(producto.description, 500) or producto.name,
        'sku': (context.get('default_variant') or {}).get('sku') or str(producto.pk),
        'brand': {'@type': 'Brand', 'name': producto.brand.name},
        'category': producto.category.name,
        'offers': oferta,
    }
    if imagenes:
        datos['image'] = imagenes
    if context['review_count']:
        datos['aggregateRating'] = {
            '@type': 'AggregateRating',
            'ratingValue': round(float(context['review_average']), 1),
            'reviewCount': context['review_count'],
        }
    nombre = gettext(producto.name)
    descripcion = gettext(producto.description) if producto.description else gettext('%(nombre)s, de la colección GoToGym.') % {'nombre': nombre}
    return contexto_seo(
        f'{nombre} | GoToGym', descripcion, tipo='product', imagen=imagenes[0] if imagenes else None,
        datos=datos,
    )
