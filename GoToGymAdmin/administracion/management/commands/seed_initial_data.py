from django.core.management.base import BaseCommand

from products.models import Brand, ProductCategory


class Command(BaseCommand):
    help = "Crea la marca y categorias iniciales de GoToGym para el panel administrador."

    categories = [
        "Conjuntos para dama",
        "Leggins",
        "Shorts para dama",
        "Tops",
        "Conjuntos para caballeros",
        "Chaquetas",
        "Sudaderas",
        "Shorts para caballeros",
    ]

    def handle(self, *args, **options):
        brand, brand_created = Brand.objects.get_or_create(name="GoToGym")
        if brand_created:
            self.stdout.write(self.style.SUCCESS("Marca creada: GoToGym"))
        else:
            self.stdout.write("Marca existente: GoToGym")

        created_count = 0
        for category_name in self.categories:
            _, created = ProductCategory.objects.get_or_create(
                name=category_name,
                defaults={"description": "Categoria base del catalogo GoToGym."},
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Categoria creada: {category_name}"))
            else:
                self.stdout.write(f"Categoria existente: {category_name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Datos iniciales listos. Categorias nuevas: {created_count}. Marca activa: {brand.name}."
            )
        )
