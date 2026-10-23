"""Carga el catalogo ampliado: 11 prendas nuevas y, junto con ellas, el orden, la visibilidad y
el inventario de los productos antiguos tal como estan en el panel local.

Es la misma logica que el comando `seed_catalog_ampliacion` (alli esta explicada por pasos), con
los datos congelados aqui: una migracion se ejecuta una vez por base de datos y no debe cambiar
si el comando evoluciona despues. Se escribio como migracion porque el comando exige entrar al
servidor, y esta se ejecuta sola con el `migrate` del arranque.

Que hace, en este orden:

1. Crea cada prenda nueva con su ficha completa (categoria, marca, descripcion, precio, variantes
   S/M/L con su SKU, inventario 0 y galeria). Si un producto con ese nombre ya existe, no lo toca;
   si faltan sus fotos en media/products, lo omite.
2. Solo si creo algun producto, alinea lo demas: reordena los 18 productos de referencia como el
   panel (cada uno ocupa uno de los huecos que ya tenian), desactiva las variantes de Pantalon
   verde y X5 Generation Mujer y pone en 0 el inventario de los 7 antiguos. Esto ultimo
   SOBRESCRIBE su stock; cada variante que cambia deja un asiento manual en el kardex con la
   cantidad anterior (delta negativo), asi que los valores previos se pueden reconstruir.

Seguridad:

- Una migracion que falla impide que la aplicacion arranque, y aqui el costo seria un sitio caido
  por un catalogo que no cargo. Por eso cualquier error se registra y se sigue: todo lo hecho en
  la corrida se deshace y la migracion queda aplicada sin cambios. En ese caso los productos se
  cargan despues con `python gotogym/manage.py seed_catalog_ampliacion` (con `--dry-run` primero).
- El ajuste `CATALOGO_AMPLIACION_EN_MIGRACION = False` la deja sin efecto. Las pruebas lo apagan
  para que la base de pruebas no cambie.
- En una base que ya tiene los productos (por ejemplo la local) no crea nada y por tanto no alinea
  nada.
- No hay reversa: deshacerla borraria productos que pudieron recibir pedidos.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import migrations, transaction
from django.db.models import Max
from django.utils import timezone

logger = logging.getLogger(__name__)

TALLAS = ("S", "M", "L")

# Igual que en el catalogo base: el stock real vive en Inventory, no en `Product.stock`.
STOCK_HEREDADO = 10

# Codigo de color de los SKU (GTG-<id>-<talla>-<color>), como en products.variant_parsing.
COLOR_SKU = {"negro": "NEG", "gris": "GRI", "blanco": "BLA", "naranja": "NAR"}

# Cada foto es (archivo en media/products, vista). La primera es la principal y lleva como texto
# alternativo el nombre del producto; las demas lo llevan seguido de " - <vista>".
PRODUCTS = [
    {
        "name": "Top ombliguero gris con panel negro para dama",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Top ombliguero de manga larga en gris con panel negro en el busto y cuello redondo negro. Para dama. Tallas S, M y L.",
        "base_price": Decimal("330000.0000"),
        "color": "gris",
        "images": [
            ("top_gris_panel_negro_dama_1.webp", None),
            ("top_gris_panel_negro_dama_2.webp", "con modelo"),
            ("top_gris_panel_negro_dama_3.webp", "con modelo"),
            ("top_gris_panel_negro_dama_4.webp", "con modelo"),
        ],
    },
    {
        "name": "Camiseta blanca con estampado geometrico para caballero",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Camiseta blanca con estampado geometrico, para caballero. Manga corta, cuello alto, cierre de cremallera frontal y paneles laterales negros. Tallas S, M y L.",
        "base_price": Decimal("330000.0000"),
        "color": "blanco",
        "images": [
            ("camiseta_blanca_geometrica_caballero_1.webp", None),
            ("camiseta_blanca_geometrica_caballero_2.webp", "con modelo"),
            ("camiseta_blanca_geometrica_caballero_3.webp", "con modelo"),
            ("camiseta_blanca_geometrica_caballero_4.webp", "con modelo"),
        ],
    },
    {
        "name": "Chaqueta gris con cremallera para caballero",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Chaqueta gris para caballero con cierre de cremallera y paneles laterales negros. Cuello alto y manga larga. Tallas S, M y L.",
        "base_price": Decimal("450000.0000"),
        "color": "gris",
        "images": [
            ("chaqueta_gris_caballero_1.webp", None),
            ("chaqueta_gris_caballero_2.webp", "vista lateral"),
            ("chaqueta_gris_caballero_3.webp", "vista de espalda"),
        ],
    },
    {
        "name": "Chaqueta blanca con estampado hexagonal para caballero",
        "category": "Sport Premium",
        "brand": "John Frank",
        "description": "Chaqueta blanca con estampado hexagonal, para caballero. Cierre de cremallera, cuello alto y manga larga. Hecha en licra con grafeno. Tallas S, M y L.",
        "base_price": Decimal("450000.0000"),
        "color": "blanco",
        "images": [
            ("chaqueta_blanca_hexagonal_caballero_1.webp", None),
            ("chaqueta_blanca_hexagonal_caballero_2.webp", "vista lateral"),
            ("chaqueta_blanca_hexagonal_caballero_3.webp", "vista de espalda"),
        ],
    },
    {
        "name": "Chaqueta negra con paneles hexagonales para caballero",
        "category": "Sport Premium",
        "brand": "John Frank",
        "description": "Chaqueta negra para caballero con cierre de cremallera con ribete blanco y paneles laterales con estampado hexagonal blanco. Cuello alto y manga larga. Tallas S, M y L.",
        "base_price": Decimal("450000.0000"),
        "color": "negro",
        "images": [
            ("chaqueta_negra_paneles_hexagonales_caballero_1.webp", None),
            ("chaqueta_negra_paneles_hexagonales_caballero_2.webp", "vista lateral"),
        ],
    },
    {
        "name": "Chaqueta negra con mangas grises para dama",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Chaqueta negra para dama con mangas grises, cierre de cremallera con ribete blanco y cuello alto. Tallas S, M y L.",
        "base_price": Decimal("330000.0000"),
        "color": "negro",
        "images": [
            ("chaqueta_negra_mangas_grises_dama_1.webp", None),
            ("chaqueta_negra_mangas_grises_dama_2.webp", "con modelo"),
            ("chaqueta_negra_mangas_grises_dama_3.webp", "con modelo"),
        ],
    },
    {
        "name": "Top ombliguero naranja con estampado geometrico para dama",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Top ombliguero de manga larga con estampado geometrico naranja, cuello redondo y banda negra en la basta. Para dama. Tallas S, M y L.",
        "base_price": Decimal("330000.0000"),
        "color": "naranja",
        "images": [
            ("top_naranja_geometrico_dama_1.webp", None),
            ("top_naranja_geometrico_dama_2.webp", "vista de espalda"),
        ],
    },
    {
        "name": "Top ombliguero blanco con estampado hexagonal para dama",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Top ombliguero blanco con estampado hexagonal, cuello alto con cierre de cremallera y manga corta. Para dama. Tallas S, M y L.",
        "base_price": Decimal("330000.0000"),
        "color": "blanco",
        "images": [
            ("top_blanco_hexagonal_dama_1.webp", None),
            ("top_blanco_hexagonal_dama_2.webp", "vista de espalda"),
        ],
    },
    {
        "name": "Conjunto para caballero en negro con azul",
        "category": "Conjuntos",
        "brand": "GoToGym",
        "description": "Conjunto de chaqueta de cuello alto con paneles laterales azules, mas mallas negras con franjas azules en diagonal. Para caballero. Tallas S, M y L.",
        "base_price": Decimal("720000.0000"),
        "color": "negro",
        "images": [
            ("conjunto_caballero_negro_azul_1.webp", None),
            ("conjunto_caballero_negro_azul_2.webp", "vista de espalda"),
        ],
    },
    {
        "name": "Blazer negro para dama",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Blazer negro para dama con solapa, cierre de un boton y bolsillos laterales. Manga larga con botones en el puno. Tallas S, M y L.",
        "base_price": Decimal("450000.0000"),
        "color": "negro",
        "images": [
            ("blazer_negro_dama_1.webp", None),
            ("blazer_negro_dama_2.webp", "vista lateral"),
            ("blazer_negro_dama_3.webp", "vista de espalda"),
        ],
    },
    {
        "name": "Conjunto negro con cuello mao para caballero",
        "category": "Conjuntos",
        "brand": "GoToGym",
        "description": "Conjunto negro para caballero: chaqueta con cuello mao, cierre de botones, bolsillos y hombreras, mas pantalon negro. Tallas S, M y L.",
        "base_price": Decimal("720000.0000"),
        "color": "negro",
        "images": [
            ("conjunto_negro_cuello_mao_caballero_1.webp", None),
            ("conjunto_negro_cuello_mao_caballero_2.webp", "vista lateral"),
            ("conjunto_negro_cuello_mao_caballero_3.webp", "vista de espalda"),
        ],
    },
]

# Orden de referencia del catalogo: el que tiene el panel local.
ORDEN_DEL_CATALOGO = (
    "Chaqueta naranja + grafeno cremallera caballero",
    "Pantalon verde",
    "Top ombliguero gris con panel negro para dama",
    "Camiseta blanca con estampado geometrico para caballero",
    "Conjunto para dama en gris con negro",
    "Conjunto gris azulado deportivo para dama",
    "X5 Generation Mujer",
    "Leggins gris azulado para dama",
    "Chaqueta gris con cremallera para caballero",
    "Chaqueta blanca con estampado hexagonal para caballero",
    "Chaqueta negra con paneles hexagonales para caballero",
    "Chaqueta negra con mangas grises para dama",
    "Top ombliguero naranja con estampado geometrico para dama",
    "Top ombliguero blanco con estampado hexagonal para dama",
    "Conjunto para caballero en negro con azul",
    "Saco negro gris",
    "Blazer negro para dama",
    "Conjunto negro con cuello mao para caballero",
)

# Productos que ya existian: los de referencia que esta migracion no crea.
_NUEVOS = {item["name"] for item in PRODUCTS}
ANTIGUOS = tuple(nombre for nombre in ORDEN_DEL_CATALOGO if nombre not in _NUEVOS)

# Productos que el panel local tiene ocultos (todas sus variantes desactivadas).
OCULTOS = ("Pantalon verde", "X5 Generation Mujer")


def reordenar(productos, clave=lambda producto: producto):
    """Devuelve `productos` con los de ORDEN_DEL_CATALOGO en ese orden.

    Los de referencia se reparten, en el orden de referencia, entre los huecos que ya ocupaban;
    los demas no se mueven (la regla con la que el panel guarda un reorden)."""
    posicion = {nombre: i for i, nombre in enumerate(ORDEN_DEL_CATALOGO)}
    huecos = [i for i, producto in enumerate(productos) if clave(producto) in posicion]
    en_orden = sorted((productos[i] for i in huecos), key=lambda producto: posicion[clave(producto)])
    resultado = list(productos)
    for hueco, producto in zip(huecos, en_orden, strict=True):
        resultado[hueco] = producto
    return resultado


def aplicar_ampliacion(apps):
    """Crea lo que falte y, si creo algo, alinea el resto. Devuelve cuantos productos creo."""
    Brand = apps.get_model("products", "Brand")
    Product = apps.get_model("products", "Product")
    ProductCategory = apps.get_model("products", "ProductCategory")
    ProductMedia = apps.get_model("products", "ProductMedia")
    ProductVariant = apps.get_model("products", "ProductVariant")
    Inventory = apps.get_model("inventory", "Inventory")
    InventoryAdjustment = apps.get_model("inventory", "InventoryAdjustment")

    creados = 0
    for item in PRODUCTS:
        if Product.objects.filter(name=item["name"]).exists():
            continue
        faltantes = [
            archivo for archivo, _ in item["images"]
            if not default_storage.exists(f"products/{archivo}")
        ]
        if faltantes:
            logger.warning("Catalogo ampliado: se omite %r, faltan fotos: %s", item["name"], ", ".join(faltantes))
            continue

        with transaction.atomic():  # un producto se crea completo o no se crea
            categoria, _ = ProductCategory.objects.get_or_create(
                name=item["category"],
                defaults={"description": "Categoria base del catalogo GoToGym."},
            )
            marca, _ = Brand.objects.get_or_create(name=item["brand"])
            # Los modelos historicos no traen el `save` propio de Product: la posicion libre
            # siguiente se calcula aqui.
            ultima = Product.objects.aggregate(ultima=Max("sort_order"))["ultima"] or 0
            producto = Product.objects.create(
                name=item["name"], category=categoria, brand=marca, description=item["description"],
                base_price=item["base_price"], discount=0, stock=STOCK_HEREDADO, featured=True,
                image=f"products/{item['images'][0][0]}", sort_order=ultima + 1,
            )
            for talla in TALLAS:
                variante = ProductVariant.objects.create(
                    product=producto, size=talla, color=item["color"],
                    sku=f"GTG-{producto.pk:04d}-{talla}-{COLOR_SKU[item['color']]}",
                )
                Inventory.objects.create(variant=variante, quantity_available=0)
            for orden, (archivo, vista) in enumerate(item["images"]):
                ProductMedia.objects.create(
                    product=producto, image=f"products/{archivo}", sort_order=orden,
                    is_primary=orden == 0,
                    alt_text=item["name"] if vista is None else f"{item['name']} - {vista}",
                )
        creados += 1

    if not creados:
        return 0

    # Orden del catalogo.
    productos = list(Product.objects.only("pk", "name", "sort_order").order_by("sort_order", "id"))
    cambiados = []
    for posicion, producto in enumerate(reordenar(productos, lambda p: p.name), start=1):
        if producto.sort_order != posicion:
            producto.sort_order = posicion
            cambiados.append(producto)
    Product.objects.bulk_update(cambiados, ["sort_order"])

    # Visibilidad: lo que el panel entiende por ocultar es desactivar todas las variantes.
    ProductVariant.objects.filter(product__name__in=OCULTOS, is_active=True).update(is_active=False)

    # Inventario de los antiguos en 0, con el asiento manual de cada variante que cambia.
    inventarios = list(
        Inventory.objects.select_for_update()
        .filter(variant__product__name__in=ANTIGUOS, quantity_available__gt=0)
        .order_by("variant_id")
    )
    if inventarios:
        Inventory.objects.filter(pk__in=[i.pk for i in inventarios]).update(
            quantity_available=0, updated_at=timezone.now(),
        )
        InventoryAdjustment.objects.bulk_create([
            InventoryAdjustment(
                inventory=inventario, delta=-inventario.quantity_available,
                quantity_after=0, reason="manual",
            )
            for inventario in inventarios
        ])
    return creados


def sembrar_catalogo_ampliado(apps, schema_editor):
    if not getattr(settings, "CATALOGO_AMPLIACION_EN_MIGRACION", True):
        return
    try:
        with transaction.atomic():
            creados = aplicar_ampliacion(apps)
    except Exception:
        logger.exception(
            "Catalogo ampliado: no se pudo cargar y se continua sin el. Cargarlo despues con "
            "`python gotogym/manage.py seed_catalog_ampliacion`."
        )
        return
    logger.warning("Catalogo ampliado: %d producto(s) creado(s).", creados)


def sin_reversa(apps, schema_editor):
    """No hay nada que deshacer: borrar estos productos eliminaria tambien lo que se haya
    vendido, fotografiado o editado de ellos despues."""


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0005_panelsettings_online_payments_enabled"),
        ("products", "0016_product_sort_order"),
        ("inventory", "0004_tildes_en_textos"),
    ]

    operations = [
        migrations.RunPython(sembrar_catalogo_ampliado, sin_reversa),
    ]
