"""Adición no destructiva: consentimiento separado para conclusiones textiles."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vendedor", "0005_experience_guidance_consent")]

    operations = [
        migrations.AddField(
            model_name="commercepersonalizationconsent",
            name="experience_conclusions",
            field=models.BooleanField(default=False),
        ),
    ]
