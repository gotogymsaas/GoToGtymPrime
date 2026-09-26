"""Auditoria de solo lectura del catalogo.

Cuenta productos, categorias, marcas y usuarios, verifica la integridad de
las variantes generadas y lista las imagenes presentes en `media/products/`
que no estan asociadas a ningun `Product`. No modifica ningun dato.

Sale con codigo 1 si detecta un problema de integridad, para poder usarse
como verificacion automatizada tras una migracion.

El resultado depende de la base de datos contra la que se ejecute (ver el
`--settings` usado): correrlo en local reporta el catalogo de desarrollo, no
el de produccion.
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from inventory.models import Inventory

from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant
from products.variant_parsing import COLOR_UNKNOWN, SIZE_UNKNOWN


class Command(BaseCommand):
    help = (
        "Auditoria de solo lectura del catalogo: cuenta productos, categorias, "
        "marcas y usuarios, y lista imagenes de media/products/ sin Product "
        "asociado. No escribe en la base de datos."
    )

    def handle(self, *args, **options):
        User = get_user_model()

        product_count = Product.objects.count()
        category_count = ProductCategory.objects.count()
        brand_count = Brand.objects.count()
        user_count = User.objects.count()
        stock_total = Product.objects.aggregate(total=Sum('stock')).get('total') or 0

        db_alias = Product.objects.db
        db_engine = settings.DATABASES[db_alias]['ENGINE']
        db_name = settings.DATABASES[db_alias]['NAME']

        self.stdout.write(self.style.MIGRATE_HEADING('Auditoria de catalogo (solo lectura)'))
        self.stdout.write(f'  Motor/BD consultada: {db_engine} -> {db_name}')
        self.stdout.write(f'  Productos:    {product_count}')
        self.stdout.write(f'  Categorias:   {category_count}')
        self.stdout.write(f'  Marcas:       {brand_count}')
        self.stdout.write(f'  Usuarios:     {user_count}')
        self.stdout.write(f'  Stock total (Product.stock, agregado): {stock_total}')

        referenced_images = {
            name.strip().replace('\\', '/').rsplit('/', 1)[-1]
            for name in Product.objects.exclude(image='').values_list('image', flat=True)
            if name
        }

        products_media_dir = settings.MEDIA_ROOT / 'products'
        orphan_files = []
        if products_media_dir.exists():
            for entry in sorted(os.listdir(products_media_dir)):
                full_path = products_media_dir / entry
                if full_path.is_file() and entry not in referenced_images:
                    orphan_files.append(entry)
        else:
            self.stdout.write(self.style.WARNING(f'  No existe el directorio {products_media_dir}'))

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Imagenes en media/products/ sin Product asociado ({len(orphan_files)})'
        ))
        if orphan_files:
            for name in orphan_files:
                self.stdout.write(f'  - {name}')
        else:
            self.stdout.write('  (ninguna)')

        self._audit_variants()

    def _audit_variants(self):
        problems = []

        variant_count = ProductVariant.objects.count()
        media_count = ProductMedia.objects.count()
        product_count = Product.objects.count()

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Integridad de variantes y media'))
        self.stdout.write(f'  Variantes:    {variant_count}')
        self.stdout.write(f'  ProductMedia: {media_count}')

        # Todo producto debe tener al menos una variante.
        sin_variantes = list(
            Product.objects.annotate(n=Count('variants')).filter(n=0).values_list('id', 'name')
        )
        if sin_variantes:
            problems.append(f'{len(sin_variantes)} producto(s) sin ninguna variante')
            for pid, name in sin_variantes:
                self.stdout.write(self.style.ERROR(f'  ! sin variante: {pid} - {name}'))

        # El SKU es unico a nivel de base de datos; se verifica igual por si la
        # restriccion no estuviera aplicada en algun entorno.
        duplicados = list(
            ProductVariant.objects.values('sku').annotate(n=Count('id')).filter(n__gt=1)
        )
        if duplicados:
            problems.append(f'{len(duplicados)} SKU(s) duplicado(s)')
            for row in duplicados:
                self.stdout.write(self.style.ERROR(f"  ! SKU duplicado: {row['sku']} x{row['n']}"))

        # Cada producto con imagen debe tener su ProductMedia equivalente.
        con_imagen = Product.objects.exclude(image='').exclude(image__isnull=True)
        sin_media = [
            (p.id, p.name) for p in con_imagen if not ProductMedia.objects.filter(product=p).exists()
        ]
        if sin_media:
            problems.append(f'{len(sin_media)} producto(s) con imagen pero sin ProductMedia')
            for pid, name in sin_media:
                self.stdout.write(self.style.ERROR(f'  ! sin media: {pid} - {name}'))

        # Media que apunta a un producto inexistente no deberia poder existir,
        # pero se comprueba por si se manipulo la base de datos a mano.
        media_huerfana = ProductMedia.objects.filter(product__isnull=True).count()
        if media_huerfana:
            problems.append(f'{media_huerfana} ProductMedia sin producto')

        # No es un error: son los productos cuyo texto no permitio deducir
        # talla ni color, y que conviene revisar a mano.
        genericas = ProductVariant.objects.filter(size=SIZE_UNKNOWN, color=COLOR_UNKNOWN)
        if genericas.exists():
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'  Variantes genericas ({SIZE_UNKNOWN}/{COLOR_UNKNOWN}) para revision manual: '
                f'{genericas.count()}'
            ))
            for variant in genericas.select_related('product'):
                self.stdout.write(f'    - {variant.sku}: {variant.product.name}')

        problems.extend(self._audit_inventory())

        self.stdout.write('')
        if problems:
            self.stderr.write(self.style.ERROR('Auditoria FALLIDA: ' + '; '.join(problems)))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(
            f'Auditoria OK: {product_count} producto(s), todos con variante, media e inventario.'
        ))

    def _audit_inventory(self):
        problems = []

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Inventario'))
        self.stdout.write(f'  Filas de inventario: {Inventory.objects.count()}')

        sin_inventario = list(
            ProductVariant.objects.filter(inventory__isnull=True).values_list('sku', flat=True)
        )
        if sin_inventario:
            problems.append(f'{len(sin_inventario)} variante(s) sin fila de inventario')
            for sku in sin_inventario:
                self.stdout.write(self.style.ERROR(f'  ! sin inventario: {sku}'))

        negativos = Inventory.objects.filter(quantity_available__lt=0).count()
        if negativos:
            problems.append(f'{negativos} fila(s) de inventario con cantidad negativa')

        # Comparacion contra el stock heredado a nivel de producto. Diverge de
        # forma legitima en cuanto haya ventas, porque Product.stock no se
        # actualiza; por eso se informa pero no se considera un fallo.
        divergentes = []
        for product in Product.objects.all():
            total = (
                Inventory.objects
                .filter(variant__product=product)
                .aggregate(total=Sum('quantity_available'))
                .get('total') or 0
            )
            if total != product.stock:
                divergentes.append((product.name, product.stock, total))

        if divergentes:
            self.stdout.write(self.style.WARNING(
                f'  Productos cuyo inventario ya no coincide con Product.stock: {len(divergentes)}'
            ))
            for name, original, actual in divergentes:
                self.stdout.write(f'    - {name}: Product.stock={original}, inventario={actual}')
        else:
            self.stdout.write('  El inventario coincide con Product.stock en todos los productos.')

        return problems
