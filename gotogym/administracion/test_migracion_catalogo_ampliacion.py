"""Migracion administracion.0006: carga el catalogo ampliado al hacer `migrate`. Lo que importa
verificar: que deja la base exactamente como el comando seed_catalog_ampliacion (es la misma
logica con los datos congelados), que no hace nada de mas en una segunda llamada, que nunca
impide que la aplicacion arranque y que la base de pruebas no la recibe."""
import importlib
import logging
import re
from io import StringIO
from unittest import mock

from django.apps import apps as registro
from django.core.management import call_command
from django.db import transaction
from django.test import SimpleTestCase, override_settings
from inventory.models import Inventory, InventoryAdjustment
from products.models import Brand, Product, ProductCategory, ProductVariant
from tienda.catalog import ORDEN_DEL_PANEL

from .management.commands import seed_catalog_ampliacion as comando
from .test_seed_catalog_ampliacion import _ConFotosTemporales, _nombres_en_orden_del_panel

migracion = importlib.import_module("administracion.migrations.0006_catalogo_ampliacion")

NOMBRES = {item["name"] for item in migracion.PRODUCTS}


def _estado_del_catalogo():
    """Todo lo que la migracion y el comando pueden tocar, en una forma comparable (los SKU se
    normalizan porque llevan el id del producto, que depende del contador de la base)."""
    estado = {}
    for producto in Product.objects.select_related("category", "brand").order_by(*ORDEN_DEL_PANEL):
        variantes = [
            (
                v.size, v.color, v.is_active, re.sub(r"GTG-\d{4}-", "GTG-NNNN-", v.sku),
                getattr(getattr(v, "inventory", None), "quantity_available", None),
                sorted(
                    (a.delta, a.quantity_after, a.reason, a.created_by_id)
                    for a in InventoryAdjustment.objects.filter(inventory__variant=v)
                ),
            )
            for v in producto.variants.order_by("id")
        ]
        medios = [
            (m.image.name, m.alt_text, m.sort_order, m.is_primary)
            for m in producto.media.order_by("sort_order", "id")
        ]
        estado[producto.name] = {
            "descripcion": producto.description, "categoria": producto.category.name,
            "marca": producto.brand.name if producto.brand else None,
            "precio": producto.base_price, "descuento": producto.discount, "stock": producto.stock,
            "destacado": producto.featured, "imagen": producto.image.name,
            "posicion": producto.sort_order, "variantes": variantes, "medios": medios,
        }
    return estado


class DatosDeLaMigracionTests(SimpleTestCase):
    def test_los_datos_congelados_coinciden_con_los_del_comando(self):
        self.assertEqual(migracion.PRODUCTS, comando.PRODUCTS)
        self.assertEqual(migracion.ORDEN_DEL_CATALOGO, comando.ORDEN_DEL_CATALOGO)
        self.assertEqual(migracion.ANTIGUOS, comando.ANTIGUOS)
        self.assertEqual(migracion.OCULTOS, comando.OCULTOS)
        self.assertEqual(migracion.TALLAS, comando.TALLAS)
        self.assertEqual(migracion.STOCK_HEREDADO, comando.STOCK_HEREDADO)

    def test_el_codigo_de_color_de_los_sku_cubre_todos_los_colores(self):
        colores = {item["color"] for item in migracion.PRODUCTS}
        self.assertLessEqual(colores, set(migracion.COLOR_SKU))

    def test_reordenar_se_comporta_como_el_del_comando(self):
        entrada = ["ajeno", *reversed(migracion.ORDEN_DEL_CATALOGO), "otro"]
        self.assertEqual(migracion.reordenar(entrada), comando.reordenar(entrada))


class MigracionCatalogoAmpliacionTests(_ConFotosTemporales):
    def setUp(self):
        super().setUp()
        categoria = ProductCategory.objects.get_or_create(name="Sport Premium")[0]
        marca = Brand.objects.get_or_create(name="GoToGym")[0]
        # Antiguos en un estado conocido: con una variante activa y 5 unidades cada una.
        for nombre in migracion.ANTIGUOS:
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

    def test_la_base_de_pruebas_no_recibe_el_catalogo_ampliado(self):
        # La bandera de settings_test deja la migracion sin efecto: ninguno de los 11 existe.
        self.assertFalse(Product.objects.filter(name__in=NOMBRES).exists())

    def test_deja_la_base_exactamente_como_el_comando(self):
        punto = transaction.savepoint()
        migracion.aplicar_ampliacion(registro)
        con_migracion = _estado_del_catalogo()
        transaction.savepoint_rollback(punto)
        self.assertFalse(Product.objects.filter(name__in=NOMBRES).exists())

        call_command("seed_catalog_ampliacion", stdout=StringIO(), stderr=StringIO())
        con_comando = _estado_del_catalogo()

        self.assertEqual(set(con_migracion), set(con_comando))
        for nombre in con_comando:
            self.assertEqual(con_migracion[nombre], con_comando[nombre], nombre)
        self.assertEqual(
            list(con_migracion), list(con_comando), "el orden del catalogo debe coincidir"
        )

    def test_crea_los_once_productos_y_alinea_los_antiguos(self):
        creados = migracion.aplicar_ampliacion(registro)

        self.assertEqual(creados, len(NOMBRES))
        nombres = _nombres_en_orden_del_panel()
        self.assertEqual([n for n in nombres if n in migracion.ORDEN_DEL_CATALOGO],
                         list(migracion.ORDEN_DEL_CATALOGO))
        for nombre in migracion.OCULTOS:
            self.assertFalse(Product.objects.get(name=nombre).variants.filter(is_active=True).exists())
        inventarios = Inventory.objects.filter(variant__product__name__in=migracion.ANTIGUOS)
        self.assertFalse(inventarios.exclude(quantity_available=0).exists())
        ajustes = InventoryAdjustment.objects.filter(inventory__in=inventarios, delta=-5)
        self.assertEqual(ajustes.count(), inventarios.count())

    def test_los_productos_nuevos_nacen_con_tres_tallas_e_inventario_en_cero(self):
        migracion.aplicar_ampliacion(registro)

        for producto in Product.objects.filter(name__in=NOMBRES):
            variantes = list(producto.variants.order_by("id"))
            self.assertEqual([v.size for v in variantes], ["S", "M", "L"], producto.name)
            for variante in variantes:
                self.assertTrue(re.fullmatch(rf"GTG-{producto.pk:04d}-[SML]-[A-Z]{{3}}", variante.sku))
                self.assertEqual(variante.inventory.quantity_available, 0)
        self.assertFalse(
            InventoryAdjustment.objects.filter(inventory__variant__product__name__in=NOMBRES).exists()
        )

    def test_una_segunda_llamada_no_cambia_nada_ni_deshace_lo_hecho_en_el_panel(self):
        migracion.aplicar_ampliacion(registro)
        ProductVariant.objects.filter(product__name=migracion.OCULTOS[1]).update(is_active=True)
        Inventory.objects.filter(variant__product__name=migracion.ANTIGUOS[0]).update(quantity_available=6)
        antes = _estado_del_catalogo()

        creados = migracion.aplicar_ampliacion(registro)

        self.assertEqual(creados, 0)
        self.assertEqual(_estado_del_catalogo(), antes)

    def test_un_producto_existente_con_ese_nombre_no_se_toca(self):
        existente = migracion.PRODUCTS[0]
        categoria = ProductCategory.objects.get_or_create(name=existente["category"])[0]
        marca = Brand.objects.get_or_create(name="Otra")[0]
        propio = Product.objects.create(
            name=existente["name"], category=categoria, brand=marca, base_price=1, description="mio",
        )

        migracion.aplicar_ampliacion(registro)

        propio.refresh_from_db()
        self.assertEqual((propio.base_price, propio.description, propio.brand.name), (1, "mio", "Otra"))
        self.assertFalse(propio.variants.exists())

    def test_sin_las_fotos_omite_el_producto_sin_fallar(self):
        item = migracion.PRODUCTS[3]
        (self.productos_dir / item["images"][-1][0]).unlink()

        with self.assertLogs(migracion.logger, level=logging.WARNING) as registro_log:
            creados = migracion.aplicar_ampliacion(registro)

        self.assertEqual(creados, len(NOMBRES) - 1)
        self.assertFalse(Product.objects.filter(name=item["name"]).exists())
        self.assertTrue(any(item["name"] in linea for linea in registro_log.output))

    def test_si_no_se_crea_ningun_producto_no_se_alinea_nada(self):
        self._correr_el_comando_dejando_todo_creado()
        orden = _nombres_en_orden_del_panel()
        Inventory.objects.filter(variant__product__name=migracion.ANTIGUOS[0]).update(quantity_available=9)

        creados = migracion.aplicar_ampliacion(registro)

        self.assertEqual(creados, 0)
        self.assertEqual(_nombres_en_orden_del_panel(), orden)
        self.assertFalse(
            Inventory.objects.filter(variant__product__name=migracion.ANTIGUOS[0]).exclude(quantity_available=9).exists()
        )

    def _correr_el_comando_dejando_todo_creado(self):
        call_command("seed_catalog_ampliacion", stdout=StringIO(), stderr=StringIO())

    # --- la envoltura que corre `migrate` -------------------------------------------------

    def test_con_la_bandera_apagada_no_hace_nada(self):
        migracion.sembrar_catalogo_ampliado(registro, None)
        self.assertFalse(Product.objects.filter(name__in=NOMBRES).exists())

    @override_settings(CATALOGO_AMPLIACION_EN_MIGRACION=True)
    def test_con_la_bandera_encendida_carga_el_catalogo(self):
        with self.assertLogs(migracion.logger, level=logging.WARNING):
            migracion.sembrar_catalogo_ampliado(registro, None)
        self.assertEqual(Product.objects.filter(name__in=NOMBRES).count(), len(NOMBRES))

    @override_settings(CATALOGO_AMPLIACION_EN_MIGRACION=True)
    def test_un_error_no_impide_que_la_migracion_termine(self):
        antes = _estado_del_catalogo()

        with mock.patch.object(migracion, "aplicar_ampliacion", side_effect=RuntimeError("fallo simulado")):
            with self.assertLogs(migracion.logger, level=logging.ERROR) as registro_log:
                migracion.sembrar_catalogo_ampliado(registro, None)  # no debe lanzar

        self.assertTrue(any("seed_catalog_ampliacion" in linea for linea in registro_log.output))
        self.assertEqual(_estado_del_catalogo(), antes)

    @override_settings(CATALOGO_AMPLIACION_EN_MIGRACION=True)
    def test_un_error_despues_de_crear_los_productos_deshace_todo_lo_de_la_corrida(self):
        antes = _estado_del_catalogo()

        # El fallo llega al alinear el orden, cuando los 11 productos ya estan creados.
        with mock.patch.object(migracion, "reordenar", side_effect=RuntimeError("fallo simulado")):
            with self.assertLogs(migracion.logger, level=logging.ERROR):
                migracion.sembrar_catalogo_ampliado(registro, None)

        self.assertFalse(Product.objects.filter(name__in=NOMBRES).exists())
        self.assertEqual(_estado_del_catalogo(), antes)

    def test_la_migracion_no_tiene_reversa_destructiva(self):
        # La reversa existe pero no borra nada.
        antes = Product.objects.count()
        migracion.sin_reversa(registro, None)
        self.assertEqual(Product.objects.count(), antes)
