from django.db import migrations, models


def reanudar_compras(apps, schema_editor):
    """El interruptor de pausa de compras sale del panel (lo reemplaza el del
    Coach). Si alguna base lo tenia en pausa, nadie podria reanudar las
    compras desde el panel, asi que se deja la tienda vendiendo."""
    PanelSettings = apps.get_model('administracion', 'PanelSettings')
    PanelSettings.objects.filter(purchases_paused=True).update(
        purchases_paused=False, purchases_paused_at=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0006_catalogo_ampliacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='panelsettings',
            name='coach_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Si está desactivado, Quantum Coach (la IA de GoToGym) no se muestra en la tienda.',
            ),
        ),
        migrations.RunPython(reanudar_compras, migrations.RunPython.noop),
    ]
