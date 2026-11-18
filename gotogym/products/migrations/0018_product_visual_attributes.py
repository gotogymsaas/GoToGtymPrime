import re
import unicodedata

from django.db import migrations, models

# Copia congelada de la deduccion de products/atributos.py: una migracion debe
# dar el mismo resultado aunque el modulo cambie despues. Solo llena vacios.
_TIPOS = (
    ('conjunto', ('conjunto', 'conjuntos', 'set', 'sets', 'kit')),
    ('blazer', ('blazer', 'blazers')),
    ('chaqueta', ('chaqueta', 'chaquetas', 'jacket', 'jackets', 'cortavientos', 'rompevientos', 'chamarra')),
    ('buzo', ('buzo', 'buzos', 'saco', 'sacos', 'hoodie', 'hoodies', 'sweater', 'sueter', 'sweatshirt')),
    ('top', ('top', 'tops', 'ombliguero', 'crop', 'bra', 'brasier', 'sosten')),
    ('camiseta', ('camiseta', 'camisetas', 'tshirt', 'polo', 'remera', 'playera', 'camisa', 'esqueleto')),
    ('leggings', ('leggins', 'leggings', 'legging', 'licra', 'lycra', 'malla')),
    ('short', ('short', 'shorts', 'pantaloneta', 'bermuda')),
    ('pantalon', ('pantalon', 'pantalones', 'jogger', 'joggers', 'pants')),
    ('falda', ('falda', 'faldas', 'skirt')),
    ('vestido', ('vestido', 'vestidos', 'dress')),
    ('accesorio', ('gorra', 'medias', 'calcetines', 'bolso', 'morral', 'guantes', 'botella', 'termo', 'banda')),
)


def _palabras(texto):
    descompuesto = unicodedata.normalize('NFKD', texto or '')
    return re.findall(r'[a-z0-9]+', ''.join(c for c in descompuesto if not unicodedata.combining(c)).lower())


def _tipo(nombre, descripcion):
    for texto in (nombre, descripcion):
        for palabra in _palabras(texto):
            for tipo, claves in _TIPOS:
                if palabra in claves:
                    return tipo
    return ''


def _deducir(nombre, descripcion):
    texto = ' '.join(_palabras(f'{nombre} {descripcion}'))
    solo_nombre = ' '.join(_palabras(nombre))
    manga = ('sin_manga' if re.search(r'(sin mangas?|esqueleto|sleeveless|tank)', texto)
             else 'larga' if re.search(r'mangas? larga|long sleeve', texto)
             else 'corta' if re.search(r'mangas? corta|short sleeve', texto) else '')
    cuello = ('capucha' if re.search(r'(capucha|hoodie|hooded)', texto)
              else 'mao' if re.search(r'cuello mao|mao', texto)
              else 'v' if re.search(r'cuello (en )?v|v neck', texto)
              else 'alto' if re.search(r'(cuello alto|cuello tortuga|turtleneck)', texto)
              else 'redondo' if re.search(r'cuello redondo|crew neck', texto) else '')
    diseno = ('estampado' if re.search(r'(estampado|estampada|print|grafico|geometrico)', solo_nombre)
              else 'bloques' if re.search(r'(paneles|panel|bloques)', solo_nombre) else '')
    return {'garment_type': _tipo(nombre, descripcion), 'sleeve': manga, 'neckline': cuello, 'pattern': diseno}


def completar_catalogo(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    productos = []
    for producto in Product.objects.all():
        cambiado = False
        for campo, valor in _deducir(producto.name, producto.description).items():
            if valor and not getattr(producto, campo):
                setattr(producto, campo, valor)
                cambiado = True
        if cambiado:
            producto.visual_attributes_origin = producto.visual_attributes_origin or 'inferido'
            productos.append(producto)
    Product.objects.bulk_update(
        productos, ['garment_type', 'sleeve', 'neckline', 'pattern', 'visual_attributes_origin'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0017_product_line'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='fit',
            field=models.CharField(blank=True, choices=[('ajustado', 'Ajustado'), ('regular', 'Regular'), ('holgado', 'Holgado')], max_length=20, verbose_name='ajuste'),
        ),
        migrations.AddField(
            model_name='product',
            name='garment_type',
            field=models.CharField(blank=True, choices=[('camiseta', 'Camiseta'), ('top', 'Top'), ('buzo', 'Buzo o saco'), ('chaqueta', 'Chaqueta'), ('blazer', 'Blazer'), ('leggings', 'Leggings'), ('pantalon', 'Pantalón'), ('short', 'Short'), ('falda', 'Falda'), ('vestido', 'Vestido'), ('conjunto', 'Conjunto'), ('accesorio', 'Accesorio')], db_index=True, max_length=20, verbose_name='tipo de prenda'),
        ),
        migrations.AddField(
            model_name='product',
            name='neckline',
            field=models.CharField(blank=True, choices=[('redondo', 'Cuello redondo'), ('v', 'Cuello en V'), ('mao', 'Cuello mao'), ('alto', 'Cuello alto'), ('capucha', 'Con capucha')], max_length=20, verbose_name='cuello'),
        ),
        migrations.AddField(
            model_name='product',
            name='pattern',
            field=models.CharField(blank=True, choices=[('liso', 'Liso'), ('estampado', 'Estampado'), ('bloques', 'Bloques de color')], max_length=20, verbose_name='diseño'),
        ),
        migrations.AddField(
            model_name='product',
            name='sleeve',
            field=models.CharField(blank=True, choices=[('sin_manga', 'Sin manga'), ('corta', 'Manga corta'), ('larga', 'Manga larga')], max_length=20, verbose_name='manga'),
        ),
        migrations.AddField(
            model_name='product',
            name='visual_attributes_origin',
            field=models.CharField(blank=True, choices=[('inferido', 'Deducido del nombre'), ('ia', 'Propuesto por IA (revisar)'), ('manual', 'Revisado en el panel')], max_length=10, verbose_name='origen de los atributos'),
        ),
        migrations.RunPython(completar_catalogo, migrations.RunPython.noop),
    ]
