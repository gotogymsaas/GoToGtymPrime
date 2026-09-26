"""Unifica la imagen del producto en ProductMedia.

El panel admin exponia dos formularios de imagen sobre el mismo producto:
el campo heredado `Product.image` (arriba, un solo archivo) y la galeria
`ProductMedia` (abajo, varias fotos con orden y "principal"). Un producto
creado o editado solo con el campo de arriba se quedaba sin ninguna fila
de ProductMedia, aunque `Product.primary_image` ya prioriza la galeria
sobre el campo heredado -- asi que ese producto terminaba sin imagen
donde de verdad se pinta el catalogo.

Esta migracion es la misma logica que 0009_seed_variants_and_media ya
aplico una vez para el catalogo que existia en ese momento (get_or_create
por producto+imagen, no duplica si ya hay una fila igual): aqui se repite
solo para productos que se crearon o editaron *despues* de esa migracion y
todavia no tienen ninguna ProductMedia.

Con esto, la interfaz del formulario deja de mostrar el campo heredado por
separado (ver ProductAdminForm/product_form.html): la galeria pasa a ser
la unica fuente de la imagen del producto, para viejo y nuevo por igual.
"""
from django.db import migrations


def backfill_media(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductMedia = apps.get_model("products", "ProductMedia")

    for product in Product.objects.filter(media__isnull=True).distinct().iterator():
        if not product.image:
            continue
        ProductMedia.objects.get_or_create(
            product=product,
            image=product.image,
            variant=None,
            defaults={
                "alt_text": product.name,
                "sort_order": 0,
                "is_primary": True,
            },
        )


def noop_reverse(apps, schema_editor):
    """No hay nada que deshacer: la fila de ProductMedia creada aqui es
    exactamente el mismo archivo que ya vivia en Product.image, revertir
    la migracion no debe borrar la unica copia de esa imagen."""


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0012_seed_default_tags"),
    ]

    operations = [
        migrations.RunPython(backfill_media, noop_reverse),
    ]
