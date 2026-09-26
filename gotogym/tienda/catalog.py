"""Datos de catalogo derivados de variantes e inventario.

Concentra el calculo de "que se muestra de un producto" (precio, tallas y
colores con stock, imagen principal) para que las vistas de listado y de
detalle partan de la misma fuente y no diverjan.
"""
from django.db.models import Prefetch
from products.models import Product, ProductMedia, ProductVariant

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


# A partir de cuantas unidades disponibles se avisa "quedan pocas
# unidades" en la ficha de producto. Un solo numero, no por producto: es
# facil de ajustar si hace falta, pero no queda expuesto en el admin
# todavia (eso es una mejora aparte, no parte de este alcance).
LOW_STOCK_THRESHOLD = 3

# Guia de tallas de referencia general (medidas del cuerpo, no de la
# prenda), en centimetros. NO son medidas propias de GoToGym: son valores
# de referencia usados de forma comun en el mercado colombiano de ropa
# deportiva/casual para mujer, el mismo publico de todo el catalogo actual
# (ver Product.objects.all(), todas las prendas son "para dama"). Deben
# reemplazarse por la tabla real de la marca en cuanto exista una medida
# propia; mientras tanto se muestran marcadas como "referencia general",
# nunca como una medida verificada de la prenda concreta.
SIZE_GUIDE_UNIDAD = 'cm'
SIZE_GUIDE = {
    'XS': {'busto': '78–82', 'cintura': '60–64', 'cadera': '84–88'},
    'S': {'busto': '83–87', 'cintura': '65–69', 'cadera': '89–93'},
    'M': {'busto': '88–93', 'cintura': '70–75', 'cadera': '94–99'},
    'L': {'busto': '94–99', 'cintura': '76–81', 'cadera': '100–105'},
    'XL': {'busto': '100–106', 'cintura': '82–88', 'cadera': '106–112'},
    'XXL': {'busto': '107–113', 'cintura': '89–95', 'cadera': '113–119'},
}


def size_guide_rows(sizes):
    """Filas de la guia de tallas para las tallas reales de un producto.

    Se devuelve en el mismo orden de SIZE_ORDER y solo para tallas que
    tienen equivalencia en la guia (UNICA, por ejemplo, no la tiene: es
    talla unica, no hay nada que tabular).
    """
    tallas_del_producto = set(sizes)
    return [
        {'size': size, **SIZE_GUIDE[size]}
        for size in SIZE_ORDER
        if size in SIZE_GUIDE and size in tallas_del_producto
    ]


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


class _ImagenDeRespaldo:
    """Envoltorio con la misma forma que `ProductMedia` (`.image`,
    `.alt_text`), para el unico caso en que un producto no tiene ninguna
    fila de galeria pero si tiene la imagen heredada `Product.image`. Sin
    esto, la plantilla de la PDP necesitaria dos rutas de renderizado
    distintas (una para ProductMedia real, otra para el campo heredado);
    con el mismo duck type, es un solo bucle en ambos casos."""

    def __init__(self, image, alt_text):
        self.image = image
        self.alt_text = alt_text


def product_gallery(product):
    """Fotos reales del producto, en el orden en que deben mostrarse.

    Nunca repite una imagen para simular una galeria de "al menos dos
    fotos": si el producto tiene una sola foto (o ninguna en ProductMedia
    pero si el campo heredado `image`), la lista tiene exactamente un
    elemento; si no tiene ninguna, la lista queda vacia y quien la
    consuma pinta su propio placeholder.
    """
    medios = list(product.media.all())
    if medios:
        return medios
    imagen = primary_image(product)
    if imagen:
        return [_ImagenDeRespaldo(image=imagen, alt_text=product.name)]
    return []


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


def curated_product_cards(limit=4):
    """Productos comprables para superficies editoriales.

    Mantiene la misma forma de tarjeta que PLP/PDP, prioriza la curaduria
    manual y completa los espacios con catalogo disponible. Centralizarlo
    evita repetir consultas y reglas en Home, pedidos y futuras campañas.
    """
    products = list(
        Product.objects
        .select_related('category', 'brand')
        .prefetch_related(
            Prefetch('variants', queryset=catalog_variants_queryset()),
            Prefetch(
                'media',
                queryset=ProductMedia.objects.order_by('-is_primary', 'sort_order', 'id'),
            ),
        )
        .filter(
            variants__is_active=True,
            variants__inventory__quantity_available__gt=0,
        )
        .distinct()
        .order_by('-featured', 'id')[:limit]
    )
    return [build_product_card(product) for product in products]


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


# --- Caracteristicas de producto (ficha) ---------------------------------
#
# La ficha solo tenia una descripcion en texto corrido y la marca. Esto la
# segmenta en tarjetas con icono, pero SOLO con lo que la propia
# descripcion o categoria ya afirman: material, corte, cierre, uso.
# Nunca una propiedad termica, medica o de rendimiento que el catalogo no
# respalde (ver PROPUESTA_HOME_STORE_QUANTUM.md, seccion 3: "Evitar...
# tecnologia revolucionaria sin evidencia"). Un producto con una
# descripcion pobre (ej. X5 Generation) simplemente saca menos tarjetas,
# nunca contenido inventado para rellenar.
#
# Cada entrada: (fragmentos a buscar en la descripcion en minuscula,
# icono de Material Icons Outlined, etiqueta corta, frase de una linea).
# El icono debe existir en el subconjunto servido
# (static/css/material_icons.css); anadir uno nuevo aqui implica
# regenerar ese subconjunto.
FEATURE_KEYWORDS = [
    (('microfibra', 'mirofibra'), 'texture', 'Microfibra',
     'Tejido ligero y de secado rápido.'),
    (('licra',), 'straighten', 'Licra elástica',
     'Se ajusta al movimiento sin perder forma.'),
    (('grafeno',), 'bolt', 'Con grafeno',
     'Material técnico incorporado en la construcción de la prenda.'),
    (('manga larga',), 'height', 'Manga larga',
     'Cobertura adicional para días frescos o post-entreno.'),
    (('ombliguera',), 'content_cut', 'Corte cropped',
     'Diseño corto, pensado para moverse con libertad.'),
    (('deportivo',), 'fitness_center', 'Uso deportivo',
     'Pensada para acompañar el entrenamiento.'),
    (('casual',), 'checkroom', 'Uso diario',
     'Tan cómoda para el gimnasio como para el resto del día.'),
]

# La categoria siempre aporta una tarjeta, incluso si la descripcion no
# dice nada mas: es el unico dato que todo producto tiene garantizado.
FEATURE_CATEGORIA = {
    'Alta costura personalizada exclusiva': ('workspace_premium', 'Edición exclusiva',
        'Diseño personalizado, fuera de la producción regular.'),
    'Sport Premium': ('workspace_premium', 'Línea premium',
        'Selección superior de materiales y construcción.'),
    'Semi Personalizada': ('design_services', 'Semi personalizada',
        'Ajustes disponibles sobre el diseño base.'),
    'Conjuntos': ('checkroom', 'Conjunto completo',
        'Piezas pensadas para combinarse entre sí.'),
}

MAX_FEATURES = 4


def product_features(producto):
    """Tarjetas de caracteristicas (icono, etiqueta, texto) para la PDP.

    Cuando dos entradas coinciden en icono se descarta la mas nueva, no
    porque sea menos cierta, sino para que la fila de tarjetas no repita
    el mismo simbolo y pierda su funcion de guiar el ojo.
    """
    texto = (producto.description or '').lower()
    iconos_usados = set()
    features = []

    feature_categoria = FEATURE_CATEGORIA.get(producto.category.name)
    if feature_categoria:
        features.append(feature_categoria)
        iconos_usados.add(feature_categoria[0])

    for fragmentos, icono, etiqueta, detalle in FEATURE_KEYWORDS:
        if len(features) >= MAX_FEATURES:
            break
        if icono in iconos_usados:
            continue
        if any(fragmento in texto for fragmento in fragmentos):
            features.append((icono, etiqueta, detalle))
            iconos_usados.add(icono)

    return [
        {'icon': icono, 'label': etiqueta, 'text': detalle}
        for icono, etiqueta, detalle in features[:MAX_FEATURES]
    ]
