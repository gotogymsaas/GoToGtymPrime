"""Explicit optional scope for commerce-safe completed experience guidance."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vendedor", "0004_display_name_consent")]

    operations = [
        migrations.AddField(
            model_name="commercepersonalizationconsent",
            name="experience_guidance",
            field=models.BooleanField(default=False),
        ),
    ]
