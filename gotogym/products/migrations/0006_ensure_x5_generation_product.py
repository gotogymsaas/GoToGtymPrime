from decimal import Decimal

from django.db import migrations


def ensure_x5_generation_product(apps, schema_editor):
    Brand = apps.get_model("products", "Brand")
    ProductCategory = apps.get_model("products", "ProductCategory")
    Product = apps.get_model("products", "Product")

    category, _ = ProductCategory.objects.get_or_create(
        name="Alta costura personalizada exclusiva",
        defaults={
            "description": "Categoria para productos GoToGym de alta costura personalizada exclusiva.",
        },
    )
    brand, _ = Brand.objects.get_or_create(name="GoToGym")
    product, created = Product.objects.get_or_create(
        name="X5 Generation Mujer",
        defaults={
            "category": category,
            "brand": brand,
            "description": "Producto GoToGym de alta costura personalizada exclusiva.",
            "price": Decimal("690000.0000"),
            "discount": 0,
            "stock": 2,
            "featured": True,
            "image": "products/X5_Generation_gris_dama.jfif",
        },
    )
    if not created:
        product.category = category
        product.brand = brand
        product.price = Decimal("690000.0000")
        product.stock = 2
        product.featured = True
        product.image = "products/X5_Generation_gris_dama.jfif"
        if not product.description:
            product.description = "Producto GoToGym de alta costura personalizada exclusiva."
        product.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0005_ensure_custom_couture_category"),
    ]

    operations = [
        migrations.RunPython(ensure_x5_generation_product, noop),
    ]
