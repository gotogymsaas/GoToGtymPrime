"""Alinea el catalogo con el estado de referencia del panel local: crea 11 prendas nuevas y deja
el orden, la visibilidad y el inventario de los productos antiguos como estan alli.

Se corre a mano una vez desplegado el codigo:

    python manage.py seed_catalog_ampliacion --dry-run
    python manage.py seed_catalog_ampliacion

Que hace, en este orden:

1. Crea cada prenda nueva con su ficha completa: categoria, marca, descripcion, precio,
   variantes S/M/L con su SKU, inventario por variante (0 unidades) y galeria de fotos. Las
   fotos ya procesadas viven en media/products/ y viajan con el codigo; el comando solo las
   referencia.
2. Orden. Los 18 productos de referencia (los 7 antiguos y los 11 nuevos) quedan en el orden del
   catalogo local. Se reparten, en ese orden, entre los huecos que ya ocupaban, igual que al
   arrastrar filas en el panel: cualquier otro producto conserva su posicion.
3. Visibilidad. Pantalon verde y X5 Generation Mujer quedan con todas sus variantes
   desactivadas, asi que dejan de verse en la tienda (es lo que el panel entiende por ocultar).
4. Inventario. Los 7 productos antiguos quedan con 0 unidades, con su asiento manual en el
   kardex por cada variante que cambia, igual que "Inventario llevado a 0" del panel. Esto
   SOBRESCRIBE el stock real que tengan.

Seguridad al repetirlo:

- Crear solo crea. Un producto cuyo nombre ya existe se omite sin tocarlo, asi los precios,
  textos o unidades que se hayan ajustado despues en el panel no se pisan al volver a correrlo
  (seed_catalog, en cambio, reescribe los campos del catalogo base: aqui no se quiere eso).
- Los pasos 2 a 4 si modifican productos que ya existian, por eso solo se aplican en la corrida
  que crea productos nuevos. Correr el comando de nuevo no deshace un reorden, una reactivacion
  ni una reposicion de stock hechos despues en el panel. Cada paso se puede omitir con
  --sin-orden, --sin-ocultar o --sin-stock-antiguos.
- Cada producto se crea completo o no se crea (transaccion por producto).
- Si falta alguna foto de un producto en el almacenamiento de archivos, ese producto se omite y
  el comando termina con error al final, en vez de publicar una ficha con imagenes rotas.
  Con --dry-run sirve como verificacion previa de que las fotos si se desplegaron.
- --dry-run no escribe nada y detalla cada cambio, incluidos los de productos existentes.

Las variantes nuevas nacen con 0 unidades, como estan hoy en el catalogo local; --stock N les da
N unidades iniciales, con su asiento en el kardex.

Vive en administracion y no en products porque necesita Inventory, y products no puede
depender de inventory (regla de capas del proyecto).
"""
from decimal import Decimal

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from inventory.models import Inventory, InventoryAdjustment, InventoryAdjustmentReason
from inventory.services import record_adjustment
from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant
from products.variant_parsing import build_sku
from tienda.catalog import ORDEN_DEL_PANEL

TALLAS = ("S", "M", "L")

# `Product.stock` es el campo heredado: el stock real vive en cada variante (Inventory). Se
# conserva con el mismo valor que ya tienen los productos del catalogo base.
STOCK_HEREDADO = 10

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

# Productos que ya existian: los de referencia que no crea este comando.
_NUEVOS = {item["name"] for item in PRODUCTS}
ANTIGUOS = tuple(nombre for nombre in ORDEN_DEL_CATALOGO if nombre not in _NUEVOS)

# Productos que el panel local tiene ocultos (todas sus variantes desactivadas).
OCULTOS = ("Pantalon verde", "X5 Generation Mujer")


def reordenar(productos, clave=lambda producto: producto):
    """Devuelve `productos` con los de ORDEN_DEL_CATALOGO en ese orden.

    Los de referencia se reparten, en el orden de referencia, entre los huecos que ya ocupaban;
    los demas no se mueven. Es la misma regla con la que el panel guarda un reorden, y repetirla
    sobre su propio resultado no cambia nada."""
    posicion = {nombre: i for i, nombre in enumerate(ORDEN_DEL_CATALOGO)}
    huecos = [i for i, producto in enumerate(productos) if clave(producto) in posicion]
    en_orden = sorted((productos[i] for i in huecos), key=lambda producto: posicion[clave(producto)])
    resultado = list(productos)
    for hueco, producto in zip(huecos, en_orden, strict=True):
        resultado[hueco] = producto
    return resultado


class Command(BaseCommand):
    help = (
        "Crea 11 prendas nuevas y alinea orden, visibilidad e inventario de los productos "
        "antiguos con el catálogo local. Los pasos sobre productos existentes solo se aplican "
        "en la corrida que crea productos. Usa --dry-run para verificar antes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Muestra qué se crearía y qué cambiaría, y verifica las fotos, sin escribir.",
        )
        parser.add_argument(
            "--stock", type=int, default=0,
            help="Unidades iniciales por variante nueva (por defecto 0, como en el catálogo local).",
        )
        parser.add_argument(
            "--sin-orden", action="store_true",
            help="No reordena el catálogo.",
        )
        parser.add_argument(
            "--sin-ocultar", action="store_true",
            help="No desactiva las variantes de Pantalon verde ni de X5 Generation Mujer.",
        )
        parser.add_argument(
            "--sin-stock-antiguos", action="store_true",
            help="No pone en 0 el inventario de los productos antiguos.",
        )

    def handle(self, *args, **options):
        stock = options["stock"]
        if stock < 0:
            raise CommandError("--stock no puede ser negativo.")
        dry_run = options["dry_run"]

        creados = existentes = 0
        por_crear = []
        sin_fotos = []

        for item in PRODUCTS:
            if Product.objects.filter(name=item["name"]).exists():
                existentes += 1
                self.stdout.write(f"Ya existe, se omite: {item['name']}")
                continue

            faltantes = [
                archivo for archivo, _ in item["images"]
                if not default_storage.exists(f"products/{archivo}")
            ]
            if faltantes:
                sin_fotos.append(item["name"])
                self.stderr.write(self.style.ERROR(
                    f"Faltan fotos, se omite: {item['name']} ({', '.join(faltantes)})"
                ))
                continue

            if dry_run:
                por_crear.append(item["name"])
                self.stdout.write(f"Crearía: {item['name']}")
                continue

            with transaction.atomic():
                self._crear_producto(item, stock)
            creados += 1
            self.stdout.write(self.style.SUCCESS(f"Creado: {item['name']}"))

        if creados or por_crear:
            if not options["sin_orden"]:
                self._ordenar(dry_run, por_crear)
            if not options["sin_ocultar"]:
                self._ocultar(dry_run)
            if not options["sin_stock_antiguos"]:
                self._vaciar_inventario_antiguos(dry_run)
        else:
            self.stdout.write(
                "Sin productos nuevos en esta corrida: no se alinean el orden, la visibilidad "
                "ni el inventario de los productos existentes."
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no se escribió nada."))
        cuenta = f"{len(por_crear)} por crear" if dry_run else f"{creados} creado(s)"
        self.stdout.write(
            f"Ampliación del catálogo: {cuenta}, {existentes} ya existente(s), "
            f"{len(sin_fotos)} omitido(s) por falta de fotos."
        )
        if sin_fotos:
            raise CommandError(
                "Hay productos sin crear porque sus fotos no están en media/products: "
                + "; ".join(sin_fotos)
            )

    def _crear_producto(self, item, stock):
        categoria, _ = ProductCategory.objects.get_or_create(
            name=item["category"],
            defaults={"description": "Categoria base del catalogo GoToGym."},
        )
        marca, _ = Brand.objects.get_or_create(name=item["brand"])
        principal = item["images"][0][0]
        producto = Product.objects.create(
            name=item["name"], category=categoria, brand=marca, description=item["description"],
            base_price=item["base_price"], discount=0, stock=STOCK_HEREDADO, featured=True,
            image=f"products/{principal}",
        )

        for talla in TALLAS:
            variante = ProductVariant.objects.create(
                product=producto, sku=build_sku(producto.pk, talla, item["color"]),
                size=talla, color=item["color"],
            )
            inventario = Inventory.objects.create(variant=variante, quantity_available=stock)
            if stock:
                record_adjustment(inventario, delta=stock, reason=InventoryAdjustmentReason.MANUAL)

        for orden, (archivo, vista) in enumerate(item["images"]):
            ProductMedia.objects.create(
                product=producto, image=f"products/{archivo}", sort_order=orden,
                is_primary=orden == 0,
                alt_text=item["name"] if vista is None else f"{item['name']} - {vista}",
            )

    def _ordenar(self, dry_run, por_crear):
        if dry_run:
            # Los productos que aun no existen se agregan al final, que es donde quedan al crearse.
            actuales = list(Product.objects.order_by(*ORDEN_DEL_PANEL).values_list("name", flat=True))
            actuales += por_crear
            final = reordenar(actuales)
            movidos = sum(1 for antes, despues in zip(actuales, final, strict=True) if antes != despues)
            self.stdout.write(f"Orden: cambiarían de posición {movidos} de {len(actuales)} producto(s).")
            for posicion, nombre in enumerate(final, start=1):
                if nombre in ORDEN_DEL_CATALOGO:
                    self.stdout.write(f"  {posicion}. {nombre}")
            return

        with transaction.atomic():
            productos = list(
                Product.objects.select_for_update()
                .only("pk", "name", "sort_order")
                .order_by(*ORDEN_DEL_PANEL)
            )
            cambiados = []
            for posicion, producto in enumerate(reordenar(productos, lambda p: p.name), start=1):
                if producto.sort_order != posicion:
                    producto.sort_order = posicion
                    cambiados.append(producto)
            Product.objects.bulk_update(cambiados, ["sort_order"])
        self.stdout.write(f"Orden: {len(cambiados)} producto(s) reubicado(s).")

    def _ocultar(self, dry_run):
        activas = ProductVariant.objects.filter(product__name__in=OCULTOS, is_active=True)
        cantidad = activas.count()
        if not dry_run and cantidad:
            activas.update(is_active=False)
        verbo = "se desactivarían" if dry_run else "desactivada(s)"
        self.stdout.write(f"Visibilidad: {cantidad} variante(s) de {' y '.join(OCULTOS)} {verbo}.")

    def _vaciar_inventario_antiguos(self, dry_run):
        with transaction.atomic():
            inventarios = Inventory.objects.filter(
                variant__product__name__in=ANTIGUOS, quantity_available__gt=0,
            ).order_by("variant_id")
            if not dry_run:
                inventarios = inventarios.select_for_update()
            a_cambiar = list(inventarios)
            unidades = sum(inventario.quantity_available for inventario in a_cambiar)
            if not dry_run and a_cambiar:
                Inventory.objects.filter(pk__in=[i.pk for i in a_cambiar]).update(
                    quantity_available=0, updated_at=timezone.now(),
                )
                InventoryAdjustment.objects.bulk_create([
                    InventoryAdjustment(
                        inventory=inventario, delta=-inventario.quantity_available,
                        quantity_after=0, reason=InventoryAdjustmentReason.MANUAL,
                    )
                    for inventario in a_cambiar
                ])
        verbo = "pasarían a 0" if dry_run else "puestas en 0"
        self.stdout.write(
            f"Inventario: {len(a_cambiar)} variante(s) de los {len(ANTIGUOS)} productos antiguos "
            f"{verbo} ({unidades} unidad(es))."
        )
