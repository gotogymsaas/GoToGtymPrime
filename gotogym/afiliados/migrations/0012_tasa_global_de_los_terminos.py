from decimal import Decimal

from django.db import migrations


def llevar_la_tasa_antigua_a_la_de_los_terminos(apps, schema_editor):
    """La tasa global arranco en 10 % y los terminos del programa prometen
    20 %. Si la configuracion sigue en el valor antiguo (nadie la edito), pasa
    a 20 %; cualquier otro valor lo puso una persona y no se toca."""
    Configuracion = apps.get_model('afiliados', 'ConfiguracionProgramaAfiliados')
    Configuracion.objects.filter(default_commission_rate=Decimal('10.00')).update(
        default_commission_rate=Decimal('20.00'),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('afiliados', '0011_comisiones_pagos_salida_y_recursos'),
    ]

    operations = [
        migrations.RunPython(llevar_la_tasa_antigua_a_la_de_los_terminos, migrations.RunPython.noop),
    ]
