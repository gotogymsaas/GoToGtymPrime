"""Migracion administracion.0010: crea tres prendas nuevas al hacer `migrate`. Lo que importa
verificar: que cada ficha queda completa y coherente con lo que haria el modelo, que las fotos
reales viajan con el codigo, que solo crea (no toca nada existente), que una segunda llamada no
hace nada, que nunca impide que la aplicacion arranque y que la base de pruebas no la recibe."""
import importlib
import logging
import tempfile
from pathlib import Path
from unittest import mock

from django.apps import apps as registro
from django.conf import settings
from django.test import TestCase, override_settings
from inventory.models import Inventory, InventoryAdjustment
from PIL import Image
from products import atributos, linea
from products.models import Brand, Product, ProductCategory, ProductVariant
from products.variant_parsing import build_sku

migracion = importlib.import_module("administracion.migrations.0010_catalogo_camiseta_enterizo_chaqueta")

NOMBRES = {item["name"] for item in migracion.PRODUCTS}
ARCHIVOS = [archivo for item in migracion.PRODUCTS for archivo, _ in item["images"]]


class DatosDeLaMigracionTests(TestCase):
    def test_las_fotos_reales_estan_en_el_repositorio_con_el_formato_del_catalogo(self):
        # Viajan con el codigo: sin ellas, en produccion la migracion omitiria las prendas.
        carpeta = Path(settings.BASE_DIR) / "media" / "products"
        for archivo in ARCHIVOS:
            with Image.open(carpeta / archivo) as imagen:
                self.assertEqual((imagen.format, imagen.size), ("WEBP", (1200, 1500)), archivo)

    def test_el_codigo_de_color_coincide_con_el_de_los_sku_del_panel(self):
        for item in migracion.PRODUCTS:
            self.assertEqual(build_sku(1, "S", item["color"]), f"GTG-0001-S-{item['sku_color']}", item["name"])

    def test_los_atributos_usan_codigos_del_vocabulario(self):
        for item in migracion.PRODUCTS:
            self.assertIn(item["line"], atributos.LINEAS)
            self.assertEqual(set(item["atributos"]), set(atributos.CAMPOS))
            for campo, valor in item["atributos"].items():
                self.assertIn(valor, atributos.codigos(atributos.CAMPOS[campo]), item["name"])

    def test_la_linea_y_el_tipo_coinciden_con_lo_que_deduce_el_modelo_del_nombre(self):
        for item in migracion.PRODUCTS:
            self.assertEqual(linea.inferir_linea(item["name"], item["description"]), item["line"])
            self.assertEqual(atributos.inferir_tipo(item["name"]), item["atributos"]["garment_type"])


class _ConFotosTemporales(TestCase):
    """Medios propios de cada prueba, con un archivo vacio por foto: la migracion solo comprueba
    que existan."""

    def setUp(self):
        directorio = tempfile.TemporaryDirectory()
        self.addCleanup(directorio.cleanup)
        self.productos_dir = Path(directorio.name) / "products"
        self.productos_dir.mkdir()
        for archivo in ARCHIVOS:
            (self.productos_dir / archivo).write_bytes(b"")
        medios = override_settings(MEDIA_ROOT=directorio.name)
        medios.enable()
        self.addCleanup(medios.disable)


def _estado():
    return [
        (
            p.name, p.description, p.base_price, p.sort_order, p.image.name,
            [(v.sku, v.size, v.color, v.is_active, v.inventory.quantity_available) for v in p.variants.order_by("id")],
            [(m.image.name, m.alt_text, m.is_primary) for m in p.media.order_by("sort_order")],
        )
        for p in Product.objects.order_by("id")
    ]


class MigracionPrendasNuevasTests(_ConFotosTemporales):
    def setUp(self):
        super().setUp()
        self.categoria = ProductCategory.objects.get_or_create(name="Sport Premium")[0]
        self.marca = Brand.objects.get_or_create(name="GoToGym")[0]
        self.existente = Product.objects.create(
            name="Producto previo", category=self.categoria, brand=self.marca, base_price=1000,
        )
        variante = ProductVariant.objects.create(product=self.existente, sku="TST-1", size="M", color="negro")
        Inventory.objects.create(variant=variante, quantity_available=7)

    def test_la_base_de_pruebas_no_recibe_las_prendas(self):
        self.assertFalse(Product.objects.filter(name__in=NOMBRES).exists())

    def test_crea_cada_prenda_con_su_ficha_completa(self):
        creados = migracion.crear_prendas(registro)

        self.assertEqual(creados, len(NOMBRES))
        for item in migracion.PRODUCTS:
            producto = Product.objects.get(name=item["name"])
            self.assertEqual(
                (producto.category.name, producto.brand.name, producto.base_price, producto.featured),
                (item["category"], item["brand"], item["base_price"], True),
            )
            self.assertEqual(producto.line, item["line"])
            self.assertEqual(producto.atributos_visuales(), item["atributos"])
            self.assertEqual(producto.visual_attributes_origin, atributos.ORIGEN_IA)
            self.assertEqual(producto.primary_image.name, f"products/{item['images'][0][0]}")
            self.assertEqual(producto.media.count(), len(item["images"]))

    def test_cada_talla_nace_con_cinco_unidades_y_su_asiento_en_el_kardex(self):
        migracion.crear_prendas(registro)

        for producto in Product.objects.filter(name__in=NOMBRES):
            variantes = list(producto.variants.order_by("id"))
            self.assertEqual([v.size for v in variantes], ["S", "M", "L"])
            for variante in variantes:
                self.assertEqual(variante.sku, build_sku(producto.pk, variante.size, variante.color))
                self.assertEqual(variante.inventory.quantity_available, 5)
                ajuste = InventoryAdjustment.objects.get(inventory__variant=variante)
                self.assertEqual((ajuste.delta, ajuste.quantity_after, ajuste.reason), (5, 5, "manual"))

    def test_quedan_al_final_del_catalogo_sin_mover_ni_tocar_lo_existente(self):
        antes = _estado()

        migracion.crear_prendas(registro)

        self.assertEqual(_estado()[: len(antes)], antes)
        posiciones = Product.objects.filter(name__in=NOMBRES).values_list("sort_order", flat=True)
        self.assertGreater(min(posiciones), self.existente.sort_order)
        self.assertEqual(len(set(posiciones)), len(NOMBRES))

    def test_una_segunda_llamada_no_cambia_nada(self):
        migracion.crear_prendas(registro)
        antes = _estado()

        self.assertEqual(migracion.crear_prendas(registro), 0)
        self.assertEqual(_estado(), antes)

    def test_un_producto_existente_con_ese_nombre_no_se_toca(self):
        propio = Product.objects.create(
            name=migracion.PRODUCTS[0]["name"], category=self.categoria, brand=self.marca,
            base_price=1, description="mio",
        )

        self.assertEqual(migracion.crear_prendas(registro), len(NOMBRES) - 1)

        propio.refresh_from_db()
        self.assertEqual((propio.base_price, propio.description), (1, "mio"))
        self.assertFalse(propio.variants.exists())

    def test_sin_las_fotos_omite_la_prenda_sin_fallar(self):
        item = migracion.PRODUCTS[1]
        (self.productos_dir / item["images"][-1][0]).unlink()

        with self.assertLogs(migracion.logger, level=logging.WARNING) as registro_log:
            creados = migracion.crear_prendas(registro)

        self.assertEqual(creados, len(NOMBRES) - 1)
        self.assertFalse(Product.objects.filter(name=item["name"]).exists())
        self.assertTrue(any(item["name"] in linea_log for linea_log in registro_log.output))

    # --- la envoltura que corre `migrate` -------------------------------------------------

    def test_con_la_bandera_apagada_no_hace_nada(self):
        migracion.sembrar_prendas(registro, None)
        self.assertFalse(Product.objects.filter(name__in=NOMBRES).exists())

    @override_settings(CATALOGO_AMPLIACION_EN_MIGRACION=True)
    def test_con_la_bandera_encendida_crea_las_prendas(self):
        with self.assertLogs(migracion.logger, level=logging.WARNING):
            migracion.sembrar_prendas(registro, None)
        self.assertEqual(Product.objects.filter(name__in=NOMBRES).count(), len(NOMBRES))

    @override_settings(CATALOGO_AMPLIACION_EN_MIGRACION=True)
    def test_un_error_a_mitad_de_corrida_deshace_todo_y_no_impide_terminar(self):
        antes = _estado()
        original = Inventory.objects.create

        def falla_en_la_ultima_prenda(**kwargs):
            if kwargs["variant"].product.name == migracion.PRODUCTS[-1]["name"]:
                raise RuntimeError("fallo simulado")
            return original(**kwargs)

        modelo_inventario = registro.get_model("inventory", "Inventory")
        with mock.patch.object(modelo_inventario.objects, "create", side_effect=falla_en_la_ultima_prenda):
            with self.assertLogs(migracion.logger, level=logging.ERROR) as registro_log:
                migracion.sembrar_prendas(registro, None)  # no debe lanzar

        self.assertTrue(any("migrate administracion 0009" in linea_log for linea_log in registro_log.output))
        self.assertEqual(_estado(), antes)

    def test_la_reversa_no_borra_nada(self):
        migracion.crear_prendas(registro)
        antes = Product.objects.count()
        migracion.sin_reversa(registro, None)
        self.assertEqual(Product.objects.count(), antes)
