from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0011_modo_de_pruebas_sin_pago'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='panelsettings',
            options={
                'permissions': [('toggle_test_mode', 'Puede encender el modo "Confirmar sin pagar (equipo)"')],
                'verbose_name': 'Configuración del panel',
                'verbose_name_plural': 'Configuración del panel',
            },
        ),
        migrations.AddField(
            model_name='panelsettings',
            name='staff_checkout_without_payment_since',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Cuándo se encendió el modo de pruebas. El modo vence 24 horas después '
                          '(ver `gotogym.ajustes_tienda.VIGENCIA_MODO_SIN_PAGO`); sin fecha se considera vencido.',
            ),
        ),
    ]
