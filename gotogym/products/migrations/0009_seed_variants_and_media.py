"""Genera variantes y media para el catalogo ya existente.

Recorre todos los productos presentes en la base de datos (no solo los del
catalogo semilla), deduce talla y color desde su texto libre y crea una
variante por combinacion, ademas de una ProductMedia primaria por cada
imagen de producto ya cargada.

Es re-ejecutable: usa get_or_create por SKU, asi que volver a aplicarla no
duplica filas. La operacion inversa es un no-op: revertir la migracion no
reconstruye variantes eliminadas.
"""
import logging

from django.db import migrations

from products.variant_parsing import COLOR_UNKNOWN, SIZE_UNKNOWN, parse_product_variants

logger = logging.getLogger(__name__)


def create_variants_and_media(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductVariant = apps.get_model("products", "ProductVariant")
    ProductMedia = apps.get_model("products", "ProductMedia")

    needs_review = []

    for product in Product.objects.all().iterator():
        parsed = parse_product_variants(product.id, product.name, product.description)

        for entry in parsed:
            ProductVariant.objects.get_or_create(
                sku=entry['sku'],
                defaults={
                    'product': product,
                    'size': entry['size'],
                    'color': entry['color'],
                    'is_active': True,
                },
            )

        if len(parsed) == 1 and parsed[0]['size'] == SIZE_UNKNOWN and parsed[0]['color'] == COLOR_UNKNOWN:
            needs_review.append(f"{product.id}: {product.name}")

        if product.image:
            ProductMedia.objects.get_or_create(
                product=product,
                image=product.image,
                variant=None,
                defaults={
                    'alt_text': product.name,
                    'sort_order': 0,
                    'is_primary': True,
                },
            )

    if needs_review:
        logger.warning(
            "Productos sin talla ni color reconocibles en el texto, "
            "quedaron con una variante generica y requieren revision manual: %s",
            "; ".join(needs_review),
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_productvariant_productmedia_and_more"),
    ]

    operations = [
        migrations.RunPython(create_variants_and_media, noop),
    ]
