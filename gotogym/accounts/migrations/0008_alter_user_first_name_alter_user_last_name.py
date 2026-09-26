"""Quita null=True de first_name/last_name (DJ001: un CharField no deberia
tener dos formas de estar "vacio", NULL y ''). 0003 agrego null=True sin
una razon documentada; esta migracion lo revierte.

Primero convierte cualquier NULL existente a '' -- sin este paso, aplicar
esto contra una base con filas NULL falla con una violacion de NOT NULL en
vez de corregir los datos.
"""
from django.db import migrations, models


def convertir_null_a_vacio(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(first_name__isnull=True).update(first_name='')
    User.objects.filter(last_name__isnull=True).update(last_name='')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_restore_local_users'),
    ]

    operations = [
        migrations.RunPython(convertir_null_a_vacio, noop),
        migrations.AlterField(
            model_name='user',
            name='first_name',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AlterField(
            model_name='user',
            name='last_name',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
