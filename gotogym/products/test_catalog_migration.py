"""Integridad del catalogo tras la generacion de variantes y media.

La base de datos de test aplica todas las migraciones, incluida la que
genera variantes para el catalogo semilla, asi que estos tests verifican el
resultado real de esa migracion.
"""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Brand, Product, ProductCategory, ProductMedia, ProductVariant
from .variant_parsing import COLOR_UNKNOWN, SIZE_UNKNOWN


class MigratedCatalogIntegrityTests(TestCase):
    def test_every_product_has_at_least_one_variant(self):
        sin_variantes = [p.name for p in Product.objects.all() if not p.variants.exists()]
        self.assertEqual(sin_variantes, [])

    def test_no_duplicate_skus(self):
        skus = list(ProductVariant.objects.values_list('sku', flat=True))
        self.assertEqual(len(skus), len(set(skus)))

    def test_every_product_with_image_has_primary_media(self):
        sin_media = [
            p.name
            for p in Product.objects.exclude(image='').exclude(image__isnull=True)
            if not p.media.filter(is_primary=True).exists()
        ]
        self.assertEqual(sin_media, [])

    def test_seeded_product_with_three_sizes_generated_three_variants(self):
        producto = Product.objects.get(name='Leggins gris azulado para dama')
        variantes = producto.variants.order_by('sku')
        self.assertEqual(variantes.count(), 3)
        self.assertEqual({v.size for v in variantes}, {'S', 'M', 'L'})
        self.assertEqual({v.color for v in variantes}, {'gris azulado'})

    def test_seeded_single_size_product_generated_one_variant(self):
        producto = Product.objects.get(name='Pantalon verde')
        self.assertEqual(producto.variants.count(), 1)
        variante = producto.variants.get()
        self.assertEqual(variante.size, SIZE_UNKNOWN)
        self.assertEqual(variante.color, 'verde')

    def test_unparseable_product_is_marked_generic_rather_than_guessed(self):
        producto = Product.objects.get(name='X5 Generation Mujer')
        variante = producto.variants.get()
        self.assertEqual(variante.size, SIZE_UNKNOWN)
        self.assertEqual(variante.color, COLOR_UNKNOWN)


class ProductVariantModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = ProductCategory.objects.create(name='Categoria variantes test')
        cls.brand = Brand.objects.create(name='Marca variantes test')
        cls.product = Product.objects.create(
            name='Producto variantes test',
            category=cls.category,
            brand=cls.brand,
            base_price=Decimal('200000.0000'),
        )

    def test_effective_price_falls_back_to_product_base_price(self):
        variant = ProductVariant.objects.create(
            product=self.product, sku='TEST-SKU-1', size='S', color='negro',
        )
        self.assertEqual(variant.effective_price, Decimal('200000.0000'))

    def test_price_override_takes_precedence(self):
        variant = ProductVariant.objects.create(
            product=self.product, sku='TEST-SKU-2', size='M', color='negro',
            price_override=Decimal('150000.0000'),
        )
        self.assertEqual(variant.effective_price, Decimal('150000.0000'))

    def test_sku_must_be_unique(self):
        ProductVariant.objects.create(
            product=self.product, sku='TEST-SKU-3', size='S', color='azul',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=self.product, sku='TEST-SKU-3', size='M', color='verde',
                )

    def test_same_size_and_color_cannot_repeat_within_a_product(self):
        ProductVariant.objects.create(
            product=self.product, sku='TEST-SKU-4', size='L', color='rojo',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=self.product, sku='TEST-SKU-5', size='L', color='rojo',
                )

    def test_media_can_be_linked_to_a_variant(self):
        variant = ProductVariant.objects.create(
            product=self.product, sku='TEST-SKU-6', size='S', color='verde',
        )
        media = ProductMedia.objects.create(
            product=self.product, variant=variant, image='products/x.jpg', is_primary=True,
        )
        self.assertEqual(variant.media.get(), media)
