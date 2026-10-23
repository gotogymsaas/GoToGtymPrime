"""seed_catalog_ampliacion: crea las fichas nuevas del catalogo y alinea el resto con el estado de
referencia. Se verifica lo que importa al correrlo en un entorno real: que repetirlo no duplica ni
pisa ajustes hechos en el panel, que --dry-run no escribe, que cada producto queda completo
(variantes, inventario, galeria), que nunca se publica una ficha cuyas fotos no estan y que los
pasos sobre productos existentes (orden, visibilidad, inventario) solo ocurren en la corrida que
crea productos y solo tocan lo que deben."""
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from inventory.models import Inventory, InventoryAdjustment, InventoryAdjustmentReason
from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant
from tienda.catalog import ORDEN_DEL_PANEL, storefront_products

from .management.commands.seed_catalog_ampliacion import (
    ANTIGUOS,
    OCULTOS,
    ORDEN_DEL_CATALOGO,
    PRODUCTS,
    reordenar,
)

NOMBRES = {item["name"] for item in PRODUCTS}
AJENO = "Producto ajeno al seed"


def _archivos_de_fotos():
    return [archivo for item in PRODUCTS for archivo, _ in item["images"]]


def _nombres_en_orden_del_panel():
    return list(Product.objects.order_by(*ORDEN_DEL_PANEL).values_list("name", flat=True))


class _ConFotosTemporales(TestCase):
    """Directorio de medios propio de cada prueba, con una foto vacia por archivo: el comando solo
    comprueba que existan, no las abre."""

    def setUp(self):
        self._directorio = tempfile.TemporaryDirectory()
        self.addCleanup(self._directorio.cleanup)
        productos = Path(self._directorio.name) / "products"
        productos.mkdir()
        for archivo in _archivos_de_fotos():
            (productos / archivo).write_bytes(b"")
        self._medios = override_settings(MEDIA_ROOT=self._directorio.name)
        self._medios.enable()
        self.addCleanup(self._medios.disable)
        self.productos_dir = productos

    def _correr(self, *args):
        salida = StringIO()
        call_command("seed_catalog_ampliacion", *args, stdout=salida, stderr=StringIO())
        return salida.getvalue()


class SeedCatalogAmpliacionTests(_ConFotosTemporales):
    def test_crea_todos_los_productos(self):
        self._correr()
        creados = set(Product.objects.filter(name__in=NOMBRES).values_list("name", flat=True))
        self.assertEqual(creados, NOMBRES)

    def test_cada_producto_queda_con_tres_tallas_e_inventario(self):
        self._correr()
        for producto in Product.objects.filter(name__in=NOMBRES):
            variantes = list(producto.variants.order_by("id"))
            self.assertEqual([v.size for v in variantes], ["S", "M", "L"], producto.name)
            self.assertEqual(len({v.color for v in variantes}), 1, producto.name)
            for variante in variantes:
                self.assertTrue(Inventory.objects.filter(variant=variante).exists(), variante.sku)

    def test_los_sku_siguen_el_formato_del_catalogo(self):
        self._correr()
        producto = Product.objects.get(name=PRODUCTS[0]["name"])
        skus = set(producto.variants.values_list("sku", flat=True))
        color = {"negro": "NEG", "gris": "GRI", "blanco": "BLA", "naranja": "NAR"}[PRODUCTS[0]["color"]]
        self.assertEqual(skus, {f"GTG-{producto.pk:04d}-{t}-{color}" for t in ("S", "M", "L")})

    def test_las_variantes_nacen_sin_unidades_y_sin_movimientos_de_kardex(self):
        self._correr()
        inventarios = Inventory.objects.filter(variant__product__name__in=NOMBRES)
        self.assertEqual(inventarios.count(), len(NOMBRES) * 3)
        self.assertFalse(inventarios.exclude(quantity_available=0).exists())
        self.assertFalse(InventoryAdjustment.objects.filter(inventory__in=inventarios).exists())

    def test_stock_da_unidades_iniciales_con_su_asiento_en_el_kardex(self):
        self._correr("--stock", "4")
        inventarios = Inventory.objects.filter(variant__product__name__in=NOMBRES)
        self.assertFalse(inventarios.exclude(quantity_available=4).exists())
        ajustes = InventoryAdjustment.objects.filter(inventory__in=inventarios)
        self.assertEqual(ajustes.count(), inventarios.count())
        self.assertEqual({(a.delta, a.quantity_after, a.reason) for a in ajustes},
                         {(4, 4, InventoryAdjustmentReason.MANUAL)})

    def test_stock_negativo_se_rechaza_sin_escribir(self):
        with self.assertRaises(CommandError):
            self._correr("--stock", "-1")
        self.assertFalse(Product.objects.filter(name__in=NOMBRES).exists())

    def test_la_galeria_tiene_una_principal_y_el_orden_del_comando(self):
        self._correr()
        for item in PRODUCTS:
            producto = Product.objects.get(name=item["name"])
            medios = list(producto.media.order_by("sort_order"))
            self.assertEqual([m.image.name for m in medios],
                             [f"products/{archivo}" for archivo, _ in item["images"]], item["name"])
            self.assertEqual([m.is_primary for m in medios], [True] + [False] * (len(medios) - 1))
            self.assertEqual(medios[0].alt_text, item["name"])
            self.assertEqual(producto.image.name, medios[0].image.name)

    def test_las_fotos_secundarias_dicen_que_vista_son(self):
        self._correr()
        item = next(i for i in PRODUCTS if len(i["images"]) > 1)
        segunda = ProductMedia.objects.get(product__name=item["name"], sort_order=1)
        self.assertEqual(segunda.alt_text, f"{item['name']} - {item['images'][1][1]}")

    def test_correrlo_dos_veces_no_duplica_nada(self):
        self._correr()
        antes = (Product.objects.count(), ProductVariant.objects.count(), ProductMedia.objects.count(),
                 Inventory.objects.count())
        salida = self._correr()
        despues = (Product.objects.count(), ProductVariant.objects.count(), ProductMedia.objects.count(),
                   Inventory.objects.count())
        self.assertEqual(antes, despues)
        self.assertIn("0 creado(s)", salida)

    def test_volver_a_correrlo_no_pisa_lo_ajustado_en_el_panel(self):
        self._correr()
        producto = Product.objects.get(name=PRODUCTS[0]["name"])
        producto.base_price = 123456
        producto.description = "Texto editado a mano."
        producto.save()
        Inventory.objects.filter(variant__product=producto).update(quantity_available=7)

        self._correr("--stock", "99")

        producto.refresh_from_db()
        self.assertEqual(producto.base_price, 123456)
        self.assertEqual(producto.description, "Texto editado a mano.")
        self.assertFalse(Inventory.objects.filter(variant__product=producto).exclude(quantity_available=7).exists())

    def test_un_producto_existente_con_ese_nombre_se_respeta(self):
        existente = PRODUCTS[0]
        categoria = ProductCategory.objects.get_or_create(name=existente["category"])[0]
        marca = Brand.objects.get_or_create(name="Otra")[0]
        Product.objects.create(name=existente["name"], category=categoria, brand=marca, base_price=1)

        salida = self._correr()

        self.assertEqual(Product.objects.filter(name=existente["name"]).count(), 1)
        self.assertIn("Ya existe", salida)
        self.assertFalse(ProductVariant.objects.filter(product__name=existente["name"]).exists())

    def test_dry_run_no_escribe_nada(self):
        antes = Product.objects.count()
        salida = self._correr("--dry-run")
        self.assertEqual(Product.objects.count(), antes)
        self.assertEqual(Inventory.objects.filter(variant__product__name__in=NOMBRES).count(), 0)
        self.assertIn("Dry-run", salida)
        self.assertIn(f"{len(NOMBRES)} por crear", salida)

    def test_sin_las_fotos_el_producto_no_se_crea_y_el_comando_falla_al_final(self):
        item = PRODUCTS[3]
        (self.productos_dir / item["images"][-1][0]).unlink()

        with self.assertRaises(CommandError) as error:
            self._correr()

        self.assertFalse(Product.objects.filter(name=item["name"]).exists())
        self.assertIn(item["name"], str(error.exception))
        # Los demas si se crearon: una foto que falta no frena el resto.
        self.assertEqual(Product.objects.filter(name__in=NOMBRES).count(), len(NOMBRES) - 1)

    def test_dry_run_tambien_avisa_de_fotos_ausentes(self):
        (self.productos_dir / PRODUCTS[0]["images"][0][0]).unlink()
        with self.assertRaises(CommandError):
            self._correr("--dry-run")
        self.assertFalse(Product.objects.filter(name__in=NOMBRES).exists())

    def test_crea_las_marcas_y_categorias_que_falten(self):
        self._correr()
        for item in PRODUCTS:
            producto = Product.objects.get(name=item["name"])
            self.assertEqual(producto.brand.name, item["brand"])
            self.assertEqual(producto.category.name, item["category"])

    def test_los_datos_comerciales_coinciden_con_el_catalogo_local(self):
        self._correr()
        for item in PRODUCTS:
            producto = Product.objects.get(name=item["name"])
            self.assertEqual(producto.base_price, item["base_price"])
            self.assertEqual(producto.description, item["description"])
            self.assertEqual(producto.discount, 0)
            self.assertTrue(producto.featured)


class SeedCatalogAmpliacionAlineacionTests(_ConFotosTemporales):
    """Orden, visibilidad e inventario de los productos que ya existian."""

    def setUp(self):
        super().setUp()
        categoria = ProductCategory.objects.get_or_create(name="Sport Premium")[0]
        marca = Brand.objects.get_or_create(name="GoToGym")[0]
        # Los antiguos pueden o no venir sembrados por las migraciones: se dejan en un estado
        # conocido (con una variante activa y 5 unidades cada una).
        for nombre in ANTIGUOS:
            producto = Product.objects.filter(name=nombre).first() or Product.objects.create(
                name=nombre, category=categoria, brand=marca, base_price=1000,
            )
            if not producto.variants.exists():
                ProductVariant.objects.create(
                    product=producto, sku=f"TST-{producto.pk}", size="UNICA", color="UNICO",
                )
            for variante in producto.variants.all():
                ProductVariant.objects.filter(pk=variante.pk).update(is_active=True)
                Inventory.objects.update_or_create(variant=variante, defaults={"quantity_available": 5})
        self.categoria, self.marca = categoria, marca

    def _crear_ajeno(self):
        ajeno = Product.objects.create(name=AJENO, category=self.categoria, brand=self.marca, base_price=1)
        variante = ProductVariant.objects.create(product=ajeno, sku="AJENO-1", size="UNICA", color="UNICO")
        Inventory.objects.create(variant=variante, quantity_available=8)
        return ajeno, variante

    # --- orden ---------------------------------------------------------------------------

    def test_el_catalogo_queda_en_el_orden_de_referencia(self):
        self._correr()
        nombres = _nombres_en_orden_del_panel()
        self.assertEqual([n for n in nombres if n in ORDEN_DEL_CATALOGO], list(ORDEN_DEL_CATALOGO))
        self.assertEqual(
            list(Product.objects.order_by("sort_order").values_list("sort_order", flat=True)),
            list(range(1, Product.objects.count() + 1)),
        )

    def test_un_producto_ajeno_conserva_su_posicion(self):
        ajeno, _ = self._crear_ajeno()
        antes = _nombres_en_orden_del_panel().index(AJENO)

        self._correr()

        self.assertEqual(_nombres_en_orden_del_panel().index(AJENO), antes)
        self.assertEqual(Product.objects.get(pk=ajeno.pk).name, AJENO)

    def test_sin_orden_deja_el_orden_como_estaba(self):
        for posicion, nombre in enumerate(reversed(ANTIGUOS), start=1):
            Product.objects.filter(name=nombre).update(sort_order=posicion)

        self._correr("--sin-orden")

        viejos = [n for n in _nombres_en_orden_del_panel() if n in ANTIGUOS]
        self.assertEqual(viejos, list(reversed(ANTIGUOS)))

    # --- visibilidad ---------------------------------------------------------------------

    def test_pantalon_verde_y_x5_quedan_ocultos_en_la_tienda(self):
        self._correr()
        for nombre in OCULTOS:
            producto = Product.objects.get(name=nombre)
            self.assertFalse(producto.variants.filter(is_active=True).exists(), nombre)
            self.assertFalse(storefront_products().filter(pk=producto.pk).exists(), nombre)

    def test_el_resto_sigue_visible(self):
        self._correr()
        visibles = set(storefront_products().values_list("name", flat=True))
        self.assertTrue((NOMBRES | (set(ANTIGUOS) - set(OCULTOS))) <= visibles)

    def test_sin_ocultar_no_desactiva_nada(self):
        self._correr("--sin-ocultar")
        for nombre in OCULTOS:
            self.assertTrue(Product.objects.get(name=nombre).variants.filter(is_active=True).exists(), nombre)

    # --- inventario ----------------------------------------------------------------------

    def test_los_antiguos_quedan_en_cero_con_su_asiento_en_el_kardex(self):
        self._correr()
        inventarios = Inventory.objects.filter(variant__product__name__in=ANTIGUOS)
        self.assertTrue(inventarios.exists())
        self.assertFalse(inventarios.exclude(quantity_available=0).exists())
        ajustes = InventoryAdjustment.objects.filter(inventory__in=inventarios, delta=-5)
        self.assertEqual(ajustes.count(), inventarios.count())
        self.assertEqual({(a.quantity_after, a.reason, a.created_by_id) for a in ajustes},
                         {(0, InventoryAdjustmentReason.MANUAL, None)})

    def test_sin_stock_antiguos_no_toca_el_inventario(self):
        self._correr("--sin-stock-antiguos")
        inventarios = Inventory.objects.filter(variant__product__name__in=ANTIGUOS)
        self.assertFalse(inventarios.exclude(quantity_available=5).exists())
        self.assertFalse(InventoryAdjustment.objects.filter(inventory__in=inventarios).exists())

    def test_un_producto_ajeno_no_pierde_stock_ni_visibilidad(self):
        _, variante = self._crear_ajeno()

        self._correr()

        variante.refresh_from_db()
        self.assertTrue(variante.is_active)
        self.assertEqual(Inventory.objects.get(variant=variante).quantity_available, 8)

    def test_si_los_antiguos_no_existen_no_falla(self):
        Product.objects.filter(name__in=ANTIGUOS).delete()

        salida = self._correr()

        self.assertIn("0 variante(s)", salida)
        self.assertEqual(Product.objects.filter(name__in=NOMBRES).count(), len(NOMBRES))

    # --- una segunda corrida no deshace lo hecho despues en el panel ---------------------

    def test_volver_a_correrlo_no_deshace_ajustes_posteriores_del_panel(self):
        self._correr()
        # Lo que alguien hace en el panel despues del despliegue.
        ProductVariant.objects.filter(product__name=OCULTOS[1]).update(is_active=True)
        Inventory.objects.filter(variant__product__name=ANTIGUOS[0]).update(quantity_available=6)
        primero, segundo = (Product.objects.get(name=n) for n in ORDEN_DEL_CATALOGO[:2])
        Product.objects.filter(pk=primero.pk).update(sort_order=segundo.sort_order)
        Product.objects.filter(pk=segundo.pk).update(sort_order=primero.sort_order)
        orden_antes = _nombres_en_orden_del_panel()

        salida = self._correr()

        self.assertEqual(_nombres_en_orden_del_panel(), orden_antes)
        self.assertTrue(Product.objects.get(name=OCULTOS[1]).variants.filter(is_active=True).exists())
        self.assertFalse(
            Inventory.objects.filter(variant__product__name=ANTIGUOS[0]).exclude(quantity_available=6).exists()
        )
        self.assertIn("no se alinean", salida)

    # --- dry-run -------------------------------------------------------------------------

    def test_dry_run_describe_los_cambios_sin_hacerlos(self):
        orden = _nombres_en_orden_del_panel()
        activas = ProductVariant.objects.filter(is_active=True).count()
        unidades = sum(Inventory.objects.values_list("quantity_available", flat=True))

        salida = self._correr("--dry-run")

        self.assertEqual(_nombres_en_orden_del_panel(), orden)
        self.assertEqual(ProductVariant.objects.filter(is_active=True).count(), activas)
        self.assertEqual(sum(Inventory.objects.values_list("quantity_available", flat=True)), unidades)
        self.assertIn("cambiarían de posición", salida)
        self.assertIn("se desactivarían", salida)
        self.assertIn("pasarían a 0", salida)
        for nombre in ORDEN_DEL_CATALOGO:
            self.assertIn(nombre, salida)


class ReferenciasDelSeedTests(SimpleTestCase):
    def test_las_listas_de_referencia_son_coherentes(self):
        self.assertEqual(len(set(ORDEN_DEL_CATALOGO)), len(ORDEN_DEL_CATALOGO))
        self.assertLessEqual(NOMBRES, set(ORDEN_DEL_CATALOGO))
        self.assertEqual(len(ANTIGUOS), 7)
        self.assertEqual(set(ANTIGUOS) | NOMBRES, set(ORDEN_DEL_CATALOGO))
        self.assertLessEqual(set(OCULTOS), set(ANTIGUOS))

    def test_no_hay_nombres_ni_archivos_repetidos(self):
        nombres = [item["name"] for item in PRODUCTS]
        self.assertEqual(len(nombres), len(set(nombres)))
        archivos = _archivos_de_fotos()
        self.assertEqual(len(archivos), len(set(archivos)))

    def test_reordenar_reparte_los_de_referencia_en_sus_huecos(self):
        actual = ["ajeno 1", ORDEN_DEL_CATALOGO[15], "ajeno 2", ORDEN_DEL_CATALOGO[1], "ajeno 3"]
        self.assertEqual(
            reordenar(actual),
            ["ajeno 1", ORDEN_DEL_CATALOGO[1], "ajeno 2", ORDEN_DEL_CATALOGO[15], "ajeno 3"],
        )

    def test_reordenar_es_idempotente_y_no_modifica_la_entrada(self):
        actual = list(reversed(ORDEN_DEL_CATALOGO)) + ["ajeno"]
        copia = list(actual)
        una_vez = reordenar(actual)
        self.assertEqual(actual, copia)
        self.assertEqual(una_vez, [*ORDEN_DEL_CATALOGO, "ajeno"])
        self.assertEqual(reordenar(una_vez), una_vez)

    def test_reordenar_acepta_una_clave(self):
        productos = [("b", ORDEN_DEL_CATALOGO[2]), ("a", ORDEN_DEL_CATALOGO[0])]
        self.assertEqual(reordenar(productos, clave=lambda p: p[1]), [productos[1], productos[0]])


class FotosDelComandoEnElRepositorioTests(TestCase):
    def test_todas_las_fotos_que_referencia_el_comando_estan_en_media_products(self):
        # Sin override: mira el MEDIA_ROOT real. Si falla, las fotos no se agregaron al
        # repositorio y el comando omitiria esos productos en el entorno desplegado.
        faltantes = [a for a in _archivos_de_fotos() if not (Path(settings.MEDIA_ROOT) / "products" / a).is_file()]
        self.assertEqual(faltantes, [])
