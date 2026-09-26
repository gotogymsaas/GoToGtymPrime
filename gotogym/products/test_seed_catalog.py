"""seed_catalog: reemplaza a las migraciones de datos como forma de sembrar
o actualizar el catalogo. Estos tests verifican justo lo que una migracion
de datos no puede garantizarse a si misma: que correrlo mas de una vez no
duplica nada, y que --dry-run de verdad no escribe."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .management.commands.seed_catalog import PRODUCTS
from .models import Product


class SeedCatalogCommandTests(TestCase):
    def test_corre_sin_romperse_y_reporta_exito(self):
        salida = StringIO()
        call_command('seed_catalog', stdout=salida)
        self.assertIn('Catalogo sembrado', salida.getvalue())

    def test_todos_los_productos_del_seed_quedan_creados(self):
        call_command('seed_catalog', stdout=StringIO())
        nombres_esperados = {item['name'] for item in PRODUCTS}
        nombres_reales = set(Product.objects.filter(name__in=nombres_esperados).values_list('name', flat=True))
        self.assertEqual(nombres_reales, nombres_esperados)

    def test_correrlo_dos_veces_no_duplica_nada(self):
        call_command('seed_catalog', stdout=StringIO())
        conteo_despues_de_una_vez = Product.objects.count()

        call_command('seed_catalog', stdout=StringIO())
        conteo_despues_de_dos_veces = Product.objects.count()

        self.assertEqual(conteo_despues_de_una_vez, conteo_despues_de_dos_veces)

    def test_dry_run_no_escribe_nada(self):
        conteo_antes = Product.objects.count()
        salida = StringIO()

        call_command('seed_catalog', '--dry-run', stdout=salida)

        self.assertEqual(Product.objects.count(), conteo_antes)
        self.assertIn('Dry-run', salida.getvalue())
