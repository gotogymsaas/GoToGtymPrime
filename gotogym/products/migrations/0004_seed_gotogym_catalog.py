from decimal import Decimal

from django.db import migrations


PRODUCTS = [
    {
        "name": "Leggins gris azulado para dama",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Leggins color gris, tallas S, M y L. Hecho en Microfibra. Uso deportivo y casual.",
        "price": Decimal("400000.0000"),
        "discount": 0,
        "stock": 20,
        "featured": True,
        "image": "products/Leggins_gris_dama.jpg",
    },
    {
        "name": "Pantalon verde",
        "category": "Semi Personalizada",
        "brand": "John Frank",
        "description": "Pantalon verde para caballero, talla unica, en licra.",
        "price": Decimal("400000.0000"),
        "discount": 0,
        "stock": 15,
        "featured": True,
        "image": "products/Pantalon_verde_caballero.webp",
    },
    {
        "name": "Chaqueta naranja + grafeno cremallera caballero",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Chaqueta naranja con grafeno, para caballero, talla unica. Cierre de cremallera. Hecha en licra.",
        "price": Decimal("450000.0000"),
        "discount": 0,
        "stock": 9,
        "featured": True,
        "image": "products/IMG_9347_2.jpg",
    },
    {
        "name": "Conjunto para dama en gris con negro",
        "category": "Conjuntos",
        "brand": "GoToGym",
        "description": "Chaqueta de color gris con negro, con cierre de cremallera, mas leggins gris con franja negra. Hecho en Microfibra. Para dama. Tallas S, M y L.",
        "price": Decimal("720000.0000"),
        "discount": 0,
        "stock": 10,
        "featured": True,
        "image": "products/WhatsApp_Image_2026-07-21_at_6.53.19_PM_9.jpeg",
    },
    {
        "name": "Conjunto gris azulado deportivo para dama",
        "category": "Conjuntos",
        "brand": "GoToGym",
        "description": "Conjunto de chaqueta ombliguera manga larga con leggins, color gris azulado con franja negra. Para dama, hecho en Mirofibra. Tallas S, M y L",
        "price": Decimal("720000.0000"),
        "discount": 0,
        "stock": 10,
        "featured": True,
        "image": "products/IMG_9286.jpg",
    },
    {
        "name": "Saco negro gris",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Saco negro con gris para dama, talla S, elaborado en Microfibra.",
        "price": Decimal("330000.0000"),
        "discount": 0,
        "stock": 10,
        "featured": True,
        "image": "products/saco_negro_gris_dama.jpg",
    },
]


def seed_catalog(apps, schema_editor):
    Brand = apps.get_model("products", "Brand")
    ProductCategory = apps.get_model("products", "ProductCategory")
    Product = apps.get_model("products", "Product")

    for item in PRODUCTS:
        category, _ = ProductCategory.objects.get_or_create(
            name=item["category"],
            defaults={"description": "Categoria base del catalogo GoToGym."},
        )
        brand, _ = Brand.objects.get_or_create(name=item["brand"])
        product, created = Product.objects.get_or_create(
            name=item["name"],
            defaults={
                "category": category,
                "brand": brand,
                "description": item["description"],
                "price": item["price"],
                "discount": item["discount"],
                "stock": item["stock"],
                "featured": item["featured"],
                "image": item["image"],
            },
        )
        if not created:
            product.category = category
            product.brand = brand
            product.description = item["description"]
            product.price = item["price"]
            product.discount = item["discount"]
            product.stock = item["stock"]
            product.featured = item["featured"]
            product.image = item["image"]
            product.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0003_alter_product_price"),
    ]

    operations = [
        migrations.RunPython(seed_catalog, noop),
    ]
