from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from blog.journal_content import POSTS
from blog.models import Category, Post


class Command(BaseCommand):
    help = (
        'Carga (o actualiza) las entradas del Journal sobre materiales avanzados y ropa deportiva '
        'funcionalizada. Es idempotente: se identifican por su slug.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-faltantes', action='store_true',
            help='Crea solo las entradas que no existen y deja intactas las ya cargadas (y sus ediciones).',
        )
        parser.add_argument(
            '--author', default='',
            help='Correo del autor. Por defecto, el primer superusuario (o staff).',
        )

    def handle(self, *args, **options):
        autor = self._autor(options['author'])
        ahora = timezone.now()
        creadas = actualizadas = omitidas = 0

        for orden, datos in enumerate(POSTS):
            if options['solo_faltantes'] and Post.objects.filter(slug=datos['slug']).exists():
                omitidas += 1
                continue
            categoria, _ = Category.objects.get_or_create(name=datos['category'])
            post, creada = Post.objects.update_or_create(
                slug=datos['slug'],
                defaults={
                    'title': datos['title'],
                    'author': autor,
                    'category': categoria,
                    'excerpt': datos['excerpt'],
                    'content': datos['content'],
                    'references': datos['references'],
                    'reading_time': datos['reading_time'],
                    'is_published': True,
                },
            )
            # `published` es auto_now_add: se escalonan las fechas con
            # update() para que el Journal muestre un orden estable.
            Post.objects.filter(pk=post.pk).update(published=ahora - timedelta(days=orden * 3))
            if creada:
                creadas += 1
            else:
                actualizadas += 1

        self.stdout.write(self.style.SUCCESS(
            f'Journal: {creadas} entradas creadas, {actualizadas} actualizadas, {omitidas} sin cambios '
            f'(autor: {autor.email}).'
        ))

    def _autor(self, email):
        User = get_user_model()
        if email:
            autor = User.objects.filter(email__iexact=email).first()
            if autor is None:
                raise CommandError(f'No existe un usuario con el correo {email}.')
            return autor
        autor = (
            User.objects.filter(is_superuser=True).order_by('pk').first()
            or User.objects.filter(is_staff=True).order_by('pk').first()
        )
        if autor is None:
            raise CommandError('No hay superusuario ni staff para asignar como autor; usa --author.')
        return autor
