"""Siembra o actualiza el catalogo base de GoToGym.

Antes esta misma logica vivia repartida en migraciones de datos
(products/migrations/0004_seed_gotogym_catalog.py y las que la siguieron
"asegurando" productos puntuales, ensure_custom_couture_category,
ensure_x5_generation_product). Una migracion corre una sola vez por base de
datos y nunca mas: no es la herramienta correcta para "que este catalogo
exista", que es una operacion que puede necesitar repetirse (un entorno
nuevo, una base restaurada, un dato corregido a mano que hay que
resembrar). Las migraciones de datos ya aplicadas en produccion NO se
tocan aqui -- reescribir o borrar una migracion que ya corrio ahi es un
riesgo real y no aporta nada; este comando es el patron a seguir de ahora
en adelante para lo que venga despues.

Idempotente: usa get_or_create y actualiza los campos si el producto ya
existe, igual que la migracion original. Correrlo dos veces no duplica
nada.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from products.models import Brand, Product, ProductCategory

PRODUCTS = [
    {
        "name": "Leggins gris azulado para dama",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Leggins color gris, tallas S, M y L. Hecho en Microfibra. Uso deportivo y casual.",
        "base_price": Decimal("400000.0000"),
        "discount": 0,
        "stock": 20,
        "featured": True,
        "image": "products/Leggins_gris_dama.jpg",
    },
    {
        "name": "Pantalon verde",
        "category": "Semi Personalizada",
        "brand": "John Frank",
        "description": "Pantalon verde para caballero, talla unica, en licra.",
        "base_price": Decimal("400000.0000"),
        "discount": 0,
        "stock": 15,
        "featured": True,
        "image": "products/Pantalon_verde_caballero.webp",
    },
    {
        "name": "Chaqueta naranja + grafeno cremallera caballero",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Chaqueta naranja con grafeno, para caballero, talla unica. Cierre de cremallera. Hecha en licra.",
        "base_price": Decimal("450000.0000"),
        "discount": 0,
        "stock": 9,
        "featured": True,
        "image": "products/IMG_9347_2.jpg",
    },
    {
        "name": "Conjunto para dama en gris con negro",
        "category": "Conjuntos",
        "brand": "GoToGym",
        "description": "Chaqueta de color gris con negro, con cierre de cremallera, mas leggins gris con franja negra. Hecho en Microfibra. Para dama. Tallas S, M y L.",
        "base_price": Decimal("720000.0000"),
        "discount": 0,
        "stock": 10,
        "featured": True,
        "image": "products/WhatsApp_Image_2026-07-21_at_6.53.19_PM_9.jpeg",
    },
    {
        "name": "Conjunto gris azulado deportivo para dama",
        "category": "Conjuntos",
        "brand": "GoToGym",
        "description": "Conjunto de chaqueta ombliguera manga larga con leggins, color gris azulado con franja negra. Para dama, hecho en Mirofibra. Tallas S, M y L",
        "base_price": Decimal("720000.0000"),
        "discount": 0,
        "stock": 10,
        "featured": True,
        "image": "products/IMG_9286.jpg",
    },
    {
        "name": "Saco negro gris",
        "category": "Sport Premium",
        "brand": "GoToGym",
        "description": "Saco negro con gris para dama, talla S, elaborado en Microfibra.",
        "base_price": Decimal("330000.0000"),
        "discount": 0,
        "stock": 10,
        "featured": True,
        "image": "products/saco_negro_gris_dama.jpg",
    },
]


class Command(BaseCommand):
    help = (
        "Siembra o actualiza el catalogo base de GoToGym (categorias, marcas "
        "y productos). Idempotente: correrlo varias veces no duplica nada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra que se crearia/actualizaria sin escribir en la base de datos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        creados, actualizados = 0, 0

        for item in PRODUCTS:
            existe = Product.objects.filter(name=item['name']).exists()

            if dry_run:
                self.stdout.write(
                    ('  actualizaria: ' if existe else '  crearia: ') + item['name']
                )
                continue

            category, _ = ProductCategory.objects.get_or_create(
                name=item['category'],
                defaults={'description': 'Categoria base del catalogo GoToGym.'},
            )
            brand, _ = Brand.objects.get_or_create(name=item['brand'])
            product, created = Product.objects.get_or_create(
                name=item['name'],
                defaults={
                    'category': category,
                    'brand': brand,
                    'description': item['description'],
                    'base_price': item['base_price'],
                    'discount': item['discount'],
                    'stock': item['stock'],
                    'featured': item['featured'],
                    'image': item['image'],
                },
            )
            if created:
                creados += 1
            else:
                product.category = category
                product.brand = brand
                product.description = item['description']
                product.base_price = item['base_price']
                product.discount = item['discount']
                product.stock = item['stock']
                product.featured = item['featured']
                product.image = item['image']
                product.save()
                actualizados += 1

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: no se escribio nada.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Catalogo sembrado: {creados} creado(s), {actualizados} actualizado(s).'
        ))
