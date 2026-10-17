"""Borra los eventos de analitica mas viejos que el plazo de retencion.

La tabla recibe un registro por evento de uso y crece sin limite. Las
preguntas de producto que responde se miran sobre ventanas recientes, asi que
conservar mas de unos meses solo la hace mas lenta. Es idempotente y se puede
programar a diario.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analitica.models import EventoAnalitica


class Command(BaseCommand):
    help = 'Elimina los eventos de analítica anteriores a --dias (180 por defecto).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=180, help='Días de eventos que se conservan.')

    def handle(self, *args, dias, **options):
        limite = timezone.now() - timedelta(days=dias)
        borrados, _ = EventoAnalitica.objects.filter(creado__lt=limite).delete()
        self.stdout.write(f'Eventos eliminados: {borrados}')
