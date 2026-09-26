from django.db import migrations

DEFAULT_TAGS = [
    ("Best Seller", "best-seller", "gold"),
    ("Nuevo", "nuevo", "accent"),
    ("Oferta", "oferta", "danger"),
    ("Destacado", "destacado", "accent"),
]


def seed_tags(apps, schema_editor):
    ProductTag = apps.get_model("products", "ProductTag")
    for name, slug, color_token in DEFAULT_TAGS:
        ProductTag.objects.get_or_create(slug=slug, defaults={"name": name, "color_token": color_token})


def remove_tags(apps, schema_editor):
    ProductTag = apps.get_model("products", "ProductTag")
    ProductTag.objects.filter(slug__in=[slug for _, slug, _ in DEFAULT_TAGS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0011_producttag_product_tags"),
    ]

    operations = [
        migrations.RunPython(seed_tags, remove_tags),
    ]
