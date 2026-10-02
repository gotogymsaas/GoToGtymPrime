"""Comandos de mantenimiento: auditoria del catalogo, checklist de seguridad
y carga de datos iniciales."""
import shutil
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from administracion.management.commands.seed_initial_data import Command as SeedInitial
from django.core.management import call_command
from django.test import TestCase, override_settings
from inventory.models import Inventory

from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant


def _correr(comando, *args):
    salida, error = StringIO(), StringIO()
    call_command(comando, *args, stdout=salida, stderr=error)
    return salida.getvalue(), error.getvalue()


class AuditCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.media = tempfile.mkdtemp(prefix='gotogym-audit-media-')
        (Path(cls.media) / 'products').mkdir()
        (Path(cls.media) / 'products' / 'huerfana.png').write_bytes(b'x')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(cls.media, ignore_errors=True)

    def _producto(self, nombre='Camiseta auditada', *, con_variante=True, stock=3, inventario=3):
        categoria, _ = ProductCategory.objects.get_or_create(name='Categoria audit')
        marca, _ = Brand.objects.get_or_create(name='Marca audit')
        producto = Product.objects.create(
            name=nombre, category=categoria, brand=marca, base_price=Decimal('50000'), stock=stock,
        )
        if con_variante:
            variante = ProductVariant.objects.create(
                product=producto, sku=f'AUD-{producto.pk}', size='M', color='negro',
            )
            if inventario is not None:
                Inventory.objects.create(variant=variante, quantity_available=inventario)
        return producto

    def test_catalogo_integro_pasa_y_lista_imagenes_huerfanas(self):
        self._producto()
        with override_settings(MEDIA_ROOT=Path(self.media)):
            salida, _ = _correr('audit_catalog')
        self.assertIn('Auditoria OK', salida)
        self.assertIn('huerfana.png', salida)

    def test_producto_sin_variantes_falla(self):
        self._producto(con_variante=False)
        with override_settings(MEDIA_ROOT=Path(self.media)):
            with self.assertRaises(SystemExit) as caso:
                _correr('audit_catalog')
        self.assertEqual(caso.exception.code, 1)

    def test_variante_sin_inventario_falla(self):
        self._producto(inventario=None)
        with override_settings(MEDIA_ROOT=Path(self.media)):
            with self.assertRaises(SystemExit):
                _correr('audit_catalog')

    def test_producto_con_imagen_pero_sin_media_falla(self):
        producto = self._producto()
        Product.objects.filter(pk=producto.pk).update(image='products/foto.png')
        with override_settings(MEDIA_ROOT=Path(self.media)):
            with self.assertRaises(SystemExit):
                _correr('audit_catalog')

    def test_con_media_asociada_no_falla(self):
        producto = self._producto()
        Product.objects.filter(pk=producto.pk).update(image='products/foto.png')
        ProductMedia.objects.create(product=producto, image='products/foto.png')
        with override_settings(MEDIA_ROOT=Path(self.media)):
            salida, _ = _correr('audit_catalog')
        self.assertIn('Auditoria OK', salida)

    def test_informa_variantes_genericas_y_stock_divergente_sin_fallar(self):
        producto = self._producto(stock=10, inventario=2)
        ProductVariant.objects.filter(product=producto).update(size='UNICA', color='UNICO')
        with override_settings(MEDIA_ROOT=Path(self.media)):
            salida, _ = _correr('audit_catalog')
        self.assertIn('revision manual', salida)
        self.assertIn('ya no coincide', salida)
        self.assertIn('Auditoria OK', salida)

    def test_sin_carpeta_de_medios_lo_avisa(self):
        self._producto()
        with override_settings(MEDIA_ROOT=Path(self.media) / 'no-existe'):
            salida, _ = _correr('audit_catalog')
        self.assertIn('No existe el directorio', salida)


class SecurityChecklistTests(TestCase):
    def test_un_entorno_inseguro_sale_con_error(self):
        with override_settings(
            DEBUG=False, SECRET_KEY='change-me', ALLOWED_HOSTS=[],
            SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
            PAYMENTS_MOCK_UI_ENABLED=True,
        ):
            with self.assertRaises(SystemExit) as caso:
                _correr('security_checklist')
        self.assertEqual(caso.exception.code, 1)

    def test_un_entorno_correcto_no_reporta_problemas(self):
        with override_settings(
            DEBUG=False, SECRET_KEY='x' * 64, ALLOWED_HOSTS=['tienda.example.com'],
            SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
            PAYMENTS_MOCK_UI_ENABLED=False,
        ):
            salida, _ = _correr('security_checklist')
        self.assertIn('Problemas (bloquean produccion): 0', salida)

    def test_en_desarrollo_las_banderas_inseguras_son_avisos_no_problemas(self):
        with override_settings(
            DEBUG=True, SECRET_KEY='x' * 64, ALLOWED_HOSTS=['*'],
            SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
        ):
            salida, _ = _correr('security_checklist')
        self.assertIn('Problemas (bloquean produccion): 0', salida)
        self.assertIn('DEBUG=True', salida)
        self.assertIn("ALLOWED_HOSTS incluye '*'", salida)


class SeedInitialDataTests(TestCase):
    def test_crea_la_marca_y_las_categorias_y_es_idempotente(self):
        # La migracion del catalogo ya crea la marca; se parte de una base
        # sin ella para cubrir tambien el alta.
        Product.objects.all().delete()
        Brand.objects.all().delete()
        salida, _ = _correr('seed_initial_data')
        self.assertTrue(Brand.objects.filter(name='GoToGym').exists())
        for nombre in SeedInitial.categories:
            self.assertTrue(ProductCategory.objects.filter(name=nombre).exists(), nombre)
        self.assertIn('Marca creada', salida)

        total = ProductCategory.objects.count()
        salida, _ = _correr('seed_initial_data')
        self.assertEqual(ProductCategory.objects.count(), total)
        self.assertIn('Marca existente', salida)
        self.assertIn('Categorias nuevas: 0', salida)
