"""Envia un correo de prueba para comprobar que el SMTP configurado entrega.

Uso: `python manage.py probar_correo tucorreo@dominio.com`. Si el backend
activo es el de consola (no hay `EMAIL_HOST`), lo dice: el correo no sale.
Sale con el diseño de marca de los correos reales, asi que sirve tambien para
ver como se ve en la bandeja."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from gotogym.correo import Correo, aviso, boton, datos, enviar_correo, parrafo


class Command(BaseCommand):
    help = 'Envía un correo de prueba al destinatario indicado.'

    def add_arguments(self, parser):
        parser.add_argument('destinatario')

    def handle(self, *args, **options):
        if not settings.EMAIL_BACKEND.endswith('smtp.EmailBackend'):
            self.stdout.write(self.style.WARNING(
                f'Backend activo: {settings.EMAIL_BACKEND}. Sin EMAIL_HOST el correo no sale de este equipo.'
            ))
        correo = Correo(
            asunto='Prueba de correo de GoToGym', titulo='El correo de GoToGym funciona',
            kicker='Prueba de correo', saludo='Hola,',
            bloques=[
                parrafo('Si lees esto, el correo de GoToGym está bien configurado.'),
                datos([
                    ('Remitente', settings.DEFAULT_FROM_EMAIL),
                    ('Servidor', getattr(settings, 'EMAIL_HOST', '') or 'consola (no sale)'),
                ]),
                aviso('Los correos de pedidos y de la cuenta salen con este mismo diseño.'),
                boton('Ir a la tienda', settings.SITIO_URL),
            ],
            pie='Recibes este correo porque pediste una prueba de envío.',
        )
        try:
            enviados = enviar_correo(options['destinatario'], correo)
        except Exception as error:
            raise CommandError(f'No se pudo enviar el correo: {error}') from error
        self.stdout.write(self.style.SUCCESS(f'Correos enviados: {enviados} (remitente {settings.DEFAULT_FROM_EMAIL})'))
