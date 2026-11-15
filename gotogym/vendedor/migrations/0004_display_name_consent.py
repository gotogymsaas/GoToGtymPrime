# Generated manually for additive Cognitive Commerce Bridge consent scope.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vendedor", "0003_tailoring_and_commerce_memory"),
    ]

    operations = [
        migrations.AddField(
            model_name="commercepersonalizationconsent",
            name="display_name",
            field=models.BooleanField(default=False),
        ),
    ]
