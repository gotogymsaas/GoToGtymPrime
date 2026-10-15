"""Envia un correo de prueba para comprobar que el SMTP configurado entrega.

Uso: `python manage.py probar_correo tucorreo@dominio.com`. Si el backend
activo es el de consola (no hay `EMAIL_HOST`), lo dice: el correo no sale."""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Envia un correo de prueba al destinatario indicado.'

    def add_arguments(self, parser):
        parser.add_argument('destinatario')

    def handle(self, *args, **options):
        if not settings.EMAIL_BACKEND.endswith('smtp.EmailBackend'):
            self.stdout.write(self.style.WARNING(
                f'Backend activo: {settings.EMAIL_BACKEND}. Sin EMAIL_HOST el correo no sale de este equipo.'
            ))
        try:
            enviados = send_mail(
                'Prueba de correo de GoToGym',
                'Si lees esto, el correo de GoToGym está bien configurado.',
                None, [options['destinatario']],
            )
        except Exception as error:
            raise CommandError(f'No se pudo enviar el correo: {error}') from error
        self.stdout.write(self.style.SUCCESS(f'Correos enviados: {enviados} (remitente {settings.DEFAULT_FROM_EMAIL})'))
