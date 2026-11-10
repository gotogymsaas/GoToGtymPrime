# Migracion aditiva: dos columnas con valor por defecto, sin tocar filas.
# Las concesiones previas quedan sin fecha y por tanto inactivas hasta que el
# usuario las vuelva a conceder: nunca se presume un permiso.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vendedor", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="commercepersonalizationconsent",
            name="commerce_memory",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="commercepersonalizationconsent",
            name="granted_at",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
