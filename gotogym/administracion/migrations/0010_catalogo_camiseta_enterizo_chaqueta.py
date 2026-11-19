"""Carga tres prendas nuevas con su ficha completa: la camiseta lila con textura hexagonal, el
conjunto enterizo negro con blazer satinado y la chaqueta gris oscuro con cremallera.

Sigue el camino de `0006_catalogo_ampliacion`: se ejecuta sola con el `migrate` del arranque y
las fotos, ya procesadas (1200x1500, webp), viajan con el codigo en media/products. A
diferencia de aquella, solo crea: no reordena el catalogo, no oculta productos ni cambia el
inventario de lo que ya existe.

Que hace por cada prenda:

- Si ya hay un producto con ese nombre (por ejemplo en la base local, donde se crearon desde el
  panel), no lo toca.
- Si falta alguna de sus fotos en el almacenamiento, la omite y lo deja en el log, en vez de
  publicar una ficha con imagenes rotas.
- Si no, la crea completa en una transaccion: ficha, atributos visuales (marcados como
  propuestos por IA para que se revisen en el panel), variantes S/M/L con su SKU, 5 unidades por
  talla con su asiento manual en el kardex y galeria. Queda al final del orden del catalogo.

Seguridad:

- Cualquier error se registra y la migracion termina igual, sin cambios: un catalogo que no
  cargo no debe impedir que la aplicacion arranque. Para reintentarlo, devolverla y aplicarla
  de nuevo (`migrate administracion 0009` y luego `migrate`): la reversa no borra nada.
- La desactiva el mismo ajuste que la 0006, `CATALOGO_AMPLIACION_EN_MIGRACION = False`, que
  settings_test usa para que la base de pruebas no cambie.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import migrations, transaction
from django.db.models import Max

logger = logging.getLogger(__name__)

TALLAS = ("S", "M", "L")
UNIDADES_POR_TALLA = 5

# Igual que en el resto del catalogo: el stock real vive en Inventory, no en `Product.stock`.
STOCK_HEREDADO = 10

# Los modelos historicos no traen el `save` de Product, que deduce la linea y los atributos del
# nombre: aqui van explicitos. `sku_color` es el codigo que da products.variant_parsing.build_sku.
PRODUCTS = [
    {
        "name": "Camiseta lila con textura hexagonal para caballero",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": (
            "Camiseta lila de manga corta para caballero, con textura hexagonal tono sobre tono "
            "en todo el tejido. Cuello redondo con ribete fino y ajuste regular que marca hombros "
            "y brazos sin apretar. Pensada para entrenar y para el día a día: combina con "
            "pantalón o licra negra. Tallas S, M y L."
        ),
        "base_price": Decimal("330000.0000"),
        "color": "lila",
        "sku_color": "LIL",
        "line": "caballero",
        "atributos": {
            "garment_type": "camiseta", "sleeve": "corta", "neckline": "redondo",
            "fit": "regular", "pattern": "liso",
        },
        "images": [
            ("camiseta_lila_hexagonal_caballero_1.webp", None),
            ("camiseta_lila_hexagonal_caballero_2.webp", "vista lateral"),
            ("camiseta_lila_hexagonal_caballero_3.webp", "con modelo"),
        ],
    },
    {
        "name": "Conjunto enterizo negro con blazer satinado para dama",
        "category": "Conjuntos",
        "brand": "GoToGym",
        "description": (
            "Conjunto negro para dama: enterizo largo ajustado con escote en V, copas con costura "
            "bajo el busto, tiras delgadas en los hombros y detalle de franjas en el centro del "
            "escote, más blazer largo con solapa y ribetes satinados, forro brillante, bolsillos "
            "con vivo y tres botones en el puño. El enterizo se usa solo para entrenar y, con el "
            "blazer encima, pasa del gimnasio a una salida. Tallas S, M y L."
        ),
        "base_price": Decimal("720000.0000"),
        "color": "negro",
        "sku_color": "NEG",
        "line": "dama",
        "atributos": {
            "garment_type": "conjunto", "sleeve": "larga", "neckline": "v",
            "fit": "ajustado", "pattern": "liso",
        },
        "images": [
            ("conjunto_enterizo_blazer_satinado_dama_1.webp", None),
            ("conjunto_enterizo_blazer_satinado_dama_2.webp", "con modelo"),
            ("conjunto_enterizo_blazer_satinado_dama_3.webp", "con modelo"),
            ("conjunto_enterizo_blazer_satinado_dama_4.webp", "vista lateral"),
            ("conjunto_enterizo_blazer_satinado_dama_5.webp", "detalle del forro del blazer"),
        ],
    },
    {
        "name": "Chaqueta gris oscuro con cremallera para caballero",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": (
            "Chaqueta gris oscuro jaspeado para caballero, con cierre de cremallera completo, "
            "cuello alto y manga larga raglán. Los paneles laterales negros estilizan la silueta "
            "y el ajuste cercano al cuerpo acompaña el movimiento. Para entrenar con frío, salir "
            "a correr o usar como capa ligera en el día a día. Tallas S, M y L."
        ),
        "base_price": Decimal("450000.0000"),
        "color": "gris oscuro",
        "sku_color": "GRI",
        "line": "caballero",
        "atributos": {
            "garment_type": "chaqueta", "sleeve": "larga", "neckline": "alto",
            "fit": "ajustado", "pattern": "bloques",
        },
        "images": [
            ("chaqueta_gris_oscuro_caballero_1.webp", None),
            ("chaqueta_gris_oscuro_caballero_2.webp", "vista lateral"),
            ("chaqueta_gris_oscuro_caballero_3.webp", "con modelo"),
        ],
    },
]


def crear_prendas(apps):
    """Crea las prendas que falten. Devuelve cuantas creo."""
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
            logger.warning("Prendas nuevas: se omite %r, faltan fotos: %s", item["name"], ", ".join(faltantes))
            continue

        with transaction.atomic():  # una prenda se crea completa o no se crea
            categoria, _ = ProductCategory.objects.get_or_create(
                name=item["category"],
                defaults={"description": "Categoria base del catalogo GoToGym."},
            )
            marca, _ = Brand.objects.get_or_create(name=item["brand"])
            ultima = Product.objects.aggregate(ultima=Max("sort_order"))["ultima"] or 0
            producto = Product.objects.create(
                name=item["name"], category=categoria, brand=marca, description=item["description"],
                base_price=item["base_price"], discount=0, stock=STOCK_HEREDADO, featured=True,
                image=f"products/{item['images'][0][0]}", sort_order=ultima + 1,
                line=item["line"], visual_attributes_origin="ia", **item["atributos"],
            )
            for talla in TALLAS:
                variante = ProductVariant.objects.create(
                    product=producto, size=talla, color=item["color"],
                    sku=f"GTG-{producto.pk:04d}-{talla}-{item['sku_color']}",
                )
                inventario = Inventory.objects.create(variant=variante, quantity_available=UNIDADES_POR_TALLA)
                InventoryAdjustment.objects.create(
                    inventory=inventario, delta=UNIDADES_POR_TALLA,
                    quantity_after=UNIDADES_POR_TALLA, reason="manual",
                )
            for orden, (archivo, vista) in enumerate(item["images"]):
                ProductMedia.objects.create(
                    product=producto, image=f"products/{archivo}", sort_order=orden,
                    is_primary=orden == 0,
                    alt_text=item["name"] if vista is None else f"{item['name']} - {vista}",
                )
        creados += 1
    return creados


def sembrar_prendas(apps, schema_editor):
    if not getattr(settings, "CATALOGO_AMPLIACION_EN_MIGRACION", True):
        return
    try:
        with transaction.atomic():
            creados = crear_prendas(apps)
    except Exception:
        logger.exception(
            "Prendas nuevas: no se pudieron cargar y se continua sin ellas. Reintentar con "
            "`manage.py migrate administracion 0009` y luego `manage.py migrate`."
        )
        return
    logger.warning("Prendas nuevas: %d producto(s) creado(s).", creados)


def sin_reversa(apps, schema_editor):
    """No hay nada que deshacer: borrar estas prendas eliminaria tambien lo que se haya vendido
    o editado de ellas despues. Por eso devolver la migracion sirve para reintentarla."""


class Migration(migrations.Migration):

    dependencies = [
        ("administracion", "0009_permisos_de_pedidos_y_usuarios"),
        ("products", "0018_product_visual_attributes"),
        ("inventory", "0004_tildes_en_textos"),
    ]

    operations = [
        migrations.RunPython(sembrar_prendas, sin_reversa),
    ]
