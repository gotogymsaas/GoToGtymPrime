# Migracion aditiva: no cambia cuentas, contrasenas, carrito ni pedidos.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="CommercePersonalizationConsent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("profile_basic", models.BooleanField(default=False)),
                ("sports_preferences", models.BooleanField(default=False)),
                ("experiences_summary", models.BooleanField(default=False)),
                ("tailoring_measurements", models.BooleanField(default=False)),
                ("version", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                             related_name="commerce_personalization_consent", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="CommerceConsentAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(max_length=64)),
                ("allowed", models.BooleanField()),
                ("consent_version", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name="commerce_consent_audit", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
