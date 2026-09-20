"""Datos de catalogo derivados de variantes e inventario.

Concentra el calculo de "que se muestra de un producto" (precio, tallas y
colores con stock, imagen principal) para que las vistas de listado y de
detalle partan de la misma fuente y no diverjan.
"""
from products.models import ProductVariant

# Orden de talla para presentacion; cualquier valor desconocido va al final.
SIZE_ORDER = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'UNICA']

# Solo para pintar el punto de color del selector. Es presentacion: un color
# sin equivalencia aqui se muestra con un gris neutro y su nombre en texto.
COLOR_SWATCHES = {
    'negro': '#101012',
    'blanco': '#f8f9fa',
    'gris': '#9aa0a6',
    'gris azulado': '#7b8a99',
    'azul': '#1d4ed8',
    'azul claro': '#60a5fa',
    'azul oscuro': '#1e3a8a',
    'verde': '#15803d',
    'naranja': '#ea580c',
    'rojo': '#b91c1c',
    'amarillo': '#eab308',
    'morado': '#7e22ce',
    'rosado': '#ec4899',
    'rosa': '#f9a8d4',
    'beige': '#d6c7a1',
}

NEUTRAL_SWATCH = '#c9ccd1'


def color_swatch(color):
    return COLOR_SWATCHES.get(color, NEUTRAL_SWATCH)


def size_sort_key(size):
    try:
        return (0, SIZE_ORDER.index(size))
    except ValueError:
        return (1, size)


def variant_stock(variant):
    """Unidades disponibles de una variante, 0 si no tiene fila de inventario."""
    inventory = getattr(variant, 'inventory', None)
    return inventory.quantity_available if inventory else 0


def catalog_variants_queryset():
    """Variantes activas con su inventario ya resuelto."""
    return (
        ProductVariant.objects
        .filter(is_active=True)
        .select_related('inventory')
        .order_by('size', 'color')
    )


def primary_image(product):
    return product.primary_image


def build_product_card(product):
    """Informacion que necesita una tarjeta del listado."""
    variants = [v for v in product.variants.all() if v.is_active]
    disponibles = [v for v in variants if variant_stock(v) > 0]

    precios = [v.effective_price for v in variants] or [product.base_price]

    return {
        'product': product,
        'image': primary_image(product),
        'price_min': min(precios),
        'price_max': max(precios),
        'has_price_range': min(precios) != max(precios),
        'sizes': sorted({v.size for v in disponibles}, key=size_sort_key),
        'colors': sorted({v.color for v in disponibles}),
        'in_stock': bool(disponibles),
        'total_stock': sum(variant_stock(v) for v in disponibles),
    }


def available_filter_values():
    """Tallas y colores que existen en el catalogo, para el panel de filtros."""
    variants = catalog_variants_queryset()
    sizes = sorted({v.size for v in variants}, key=size_sort_key)
    colors = sorted({v.color for v in variants})
    return sizes, colors


def build_variant_matrix(product):
    """Estructura talla -> color -> datos de la variante, para la ficha.

    Se entrega completa al template para que los selectores puedan pintarse y
    actualizarse sin pedir nada al servidor.
    """
    variants = [v for v in product.variants.all() if v.is_active]

    filas = []
    for variant in sorted(variants, key=lambda v: (size_sort_key(v.size), v.color)):
        stock = variant_stock(variant)
        filas.append({
            'id': variant.id,
            'sku': variant.sku,
            'size': variant.size,
            'color': variant.color,
            'price': variant.effective_price,
            'available': stock > 0,
            'stock': stock,
        })
    return filas
