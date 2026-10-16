from django.db import migrations


def pasar_a_mayusculas(apps, schema_editor):
    """`get_usable_coupon` busca en mayusculas: un cupon guardado en minusculas
    nunca se podia usar. Si el codigo en mayusculas ya existe se deja como esta
    (no se puede renombrar sin chocar con el otro cupon)."""
    Coupon = apps.get_model('orders', 'Coupon')
    existentes = set(Coupon.objects.values_list('code', flat=True))
    for cupon in Coupon.objects.all():
        normalizado = cupon.code.strip().upper()
        if normalizado == cupon.code or normalizado in existentes:
            continue
        existentes.discard(cupon.code)
        existentes.add(normalizado)
        Coupon.objects.filter(pk=cupon.pk).update(code=normalizado)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_integridad_y_auditoria'),
    ]

    operations = [
        migrations.RunPython(pasar_a_mayusculas, migrations.RunPython.noop),
    ]
