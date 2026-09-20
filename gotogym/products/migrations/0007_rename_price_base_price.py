from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0006_ensure_x5_generation_product"),
    ]

    operations = [
        migrations.RenameField(
            model_name="product",
            old_name="price",
            new_name="base_price",
        ),
    ]
