import re
import unicodedata

from django.db import migrations, models

# Copia congelada de products/linea.py: una migracion debe dar el mismo
# resultado aunque el modulo cambie despues.
_PALABRAS = {
    'dama': {'dama', 'damas', 'mujer', 'mujeres', 'femenino', 'femenina', 'women', 'woman', 'womens'},
    'caballero': {'caballero', 'caballeros', 'hombre', 'hombres', 'masculino', 'masculina', 'men', 'man', 'mens'},
}


def _linea_de(texto):
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    palabras = set(re.findall(r'[a-z]+', ''.join(c for c in descompuesto if not unicodedata.combining(c)).lower()))
    if 'unisex' in palabras:
        return 'unisex'
    dama = bool(palabras & _PALABRAS['dama'])
    caballero = bool(palabras & _PALABRAS['caballero'])
    if dama and caballero:
        return None
    return 'dama' if dama else 'caballero' if caballero else ''


def clasificar_catalogo(apps, schema_editor):
    """Clasifica cada producto por lo que dice su nombre (o, si el nombre no
    lo dice, su descripcion). Los que no lo dicen con certeza quedan sin
    clasificar para revisarlos en el panel."""
    Product = apps.get_model('products', 'Product')
    productos = []
    for producto in Product.objects.filter(line=''):
        del_nombre = _linea_de(producto.name)
        linea = '' if del_nombre is None else (del_nombre or _linea_de(producto.description) or '')
        if linea:
            producto.line = linea
            productos.append(producto)
    Product.objects.bulk_update(productos, ['line'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0016_product_sort_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='line',
            field=models.CharField(
                blank=True, choices=[('dama', 'Dama'), ('caballero', 'Caballero'), ('unisex', 'Unisex')],
                db_index=True, max_length=10, verbose_name='línea',
            ),
        ),
        migrations.RunPython(clasificar_catalogo, migrations.RunPython.noop),
    ]
