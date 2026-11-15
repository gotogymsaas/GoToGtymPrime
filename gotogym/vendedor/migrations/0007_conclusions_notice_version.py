"""Additive evidence of approved separate scope notice, no historic consent rewrite."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vendedor", "0006_experience_conclusions_consent")]

    operations = [
        migrations.AddField(
            model_name="commerceconsentauditevent",
            name="notice_version",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
    ]
