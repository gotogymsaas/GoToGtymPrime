"""Reparte `Product.stock` entre las variantes generadas para ese producto.

Es una aproximacion explicita: el stock heredado esta a nivel de producto, no
por talla/color, asi que se reparte lo mas parejo posible (ej. stock=20 con 3
variantes -> 7/7/6). No es una medicion real de inventario por variante, que
hoy no existe en ningun sitio.

Re-ejecutable: usa get_or_create por variante, asi que una segunda corrida no
vuelve a sumar cantidades.
"""
from django.db import migrations


def seed_inventory(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Inventory = apps.get_model("inventory", "Inventory")

    for product in Product.objects.all().iterator():
        variants = list(product.variants.order_by('id'))
        if not variants:
            continue

        count = len(variants)
        base = product.stock // count
        remainder = product.stock % count

        for index, variant in enumerate(variants):
            quantity = base + (1 if index < remainder else 0)
            Inventory.objects.get_or_create(
                variant=variant,
                defaults={'quantity_available': quantity, 'quantity_reserved': 0},
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
        ("products", "0009_seed_variants_and_media"),
    ]

    operations = [
        migrations.RunPython(seed_inventory, noop),
    ]
