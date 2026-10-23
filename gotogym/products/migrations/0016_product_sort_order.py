from django.db import migrations, models


def numerar_productos(apps, schema_editor):
    """Conserva el orden con que la tienda ya listaba los productos (por id):
    sin esto todos arrancarian en 0 y el catalogo cambiaria de orden solo."""
    Product = apps.get_model('products', 'Product')
    productos = list(Product.objects.order_by('id'))
    for posicion, producto in enumerate(productos, start=1):
        producto.sort_order = posicion
    Product.objects.bulk_update(productos, ['sort_order'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0015_integridad_y_auditoria'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='sort_order',
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.RunPython(numerar_productos, migrations.RunPython.noop),
    ]
