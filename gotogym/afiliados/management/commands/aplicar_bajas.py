"""Da de baja a los afiliados que ya cumplieron los 15 dias de preaviso.

Idempotente. El codigo de un afiliado con preaviso vencido ya deja de
aceptarse aunque este comando no se haya ejecutado (ver
`afiliados.services.afiliado_operativo`); esto solo pone al dia su estado."""
from django.core.management.base import BaseCommand

from afiliados.services import aplicar_bajas_vencidas


class Command(BaseCommand):
    help = 'Aplica las bajas de afiliados cuyo preaviso venció.'

    def handle(self, *args, **options):
        self.stdout.write(f'Bajas aplicadas: {aplicar_bajas_vencidas()}')
