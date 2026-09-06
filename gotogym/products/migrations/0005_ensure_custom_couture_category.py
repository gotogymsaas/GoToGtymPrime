from django.db import migrations


def ensure_category(apps, schema_editor):
    ProductCategory = apps.get_model("products", "ProductCategory")
    ProductCategory.objects.get_or_create(
        name="Alta costura personalizada exclusiva",
        defaults={
            "description": "Categoria para productos GoToGym de alta costura personalizada exclusiva.",
        },
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0004_seed_gotogym_catalog"),
    ]

    operations = [
        migrations.RunPython(ensure_category, noop),
    ]
