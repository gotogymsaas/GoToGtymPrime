"""Genera todos los correos de GoToGym con datos de muestra para revisar su diseño.

Uso:

    python manage.py previsualizar_correos                       # escribe HTML en ./vista_previa_correos
    python manage.py previsualizar_correos --idioma en           # los correos del pedido en ingles
    python manage.py previsualizar_correos --enviar yo@correo.com  # ademas los manda a una bandeja real

Recorre los mismos caminos de codigo que los correos reales. Los datos de
muestra (cliente, pedido, afiliado) se crean dentro de una transaccion que se
revierte al terminar: no queda nada en la base. Si hay productos con stock se
usa uno real, para ver su foto.

Los archivos HTML apuntan a las imagenes locales del proyecto; un correo
enviado con `--enviar` lleva las direcciones publicas de `SITIO_URL`.
"""
import secrets
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from afiliados import correos as correos_afiliados
from afiliados.models import (
    Commission,
    EstadoAfiliado,
    MotivoSalida,
    PerfilAfiliado,
    WithdrawalRequest,
    WithdrawalStatus,
)
from afiliados.services import notify_commission_paid
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone, translation
from inventory.models import Inventory
from orders import correos as correos_pedido
from orders.models import Coupon, CouponDiscountType, OrderStatus, PaymentStatus
from orders.services import create_order_from_cart
from products.models import Brand, Product, ProductCategory, ProductVariant

BACKEND_EN_MEMORIA = 'django.core.mail.backends.locmem.EmailBackend'

DATOS_ENTREGA = {
    'first_name': 'Camila', 'last_name': 'Rojas', 'email': 'camila@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20', 'address_complement': 'Apto 502',
}


class Command(BaseCommand):
    help = 'Genera todos los correos con datos de muestra para revisar su diseño (no deja datos en la base).'

    def add_arguments(self, parser):
        parser.add_argument('--carpeta', default='vista_previa_correos', help='Donde escribir los archivos HTML.')
        parser.add_argument('--idioma', default='es', choices=[codigo for codigo, _ in settings.LANGUAGES])
        parser.add_argument('--enviar', metavar='CORREO', help='Manda tambien cada correo a esta bandeja.')

    def handle(self, *args, **options):
        idioma = options['idioma']
        carpeta = Path(options['carpeta'])
        original = settings.EMAIL_BACKEND

        # La bandeja en memoria es global (la usan tambien las pruebas): se
        # deja como estaba al terminar.
        bandeja_previa = getattr(mail, 'outbox', None)
        try:
            with override_settings(EMAIL_BACKEND=BACKEND_EN_MEMORIA):
                mail.outbox = []
                with transaction.atomic():
                    capturados = self._generar(idioma)
                    transaction.set_rollback(True)
        finally:
            if bandeja_previa is None:
                if hasattr(mail, 'outbox'):
                    del mail.outbox
            else:
                mail.outbox = bandeja_previa

        if not capturados:
            raise CommandError('No se generó ningún correo.')
        self._escribir(carpeta, capturados)
        self.stdout.write(self.style.SUCCESS(
            f'{len(capturados)} correos en {carpeta.resolve()} (abre index.html en el navegador).'
        ))

        if options['enviar']:
            self._enviar(capturados, options['enviar'], original)

    # --- Generacion ---------------------------------------------------------

    def _generar(self, idioma):
        capturados = []

        def capturar(etiqueta, accion):
            mail.outbox.clear()
            accion()
            if not mail.outbox:
                raise CommandError(f'"{etiqueta}" no produjo ningún correo.')
            capturados.append((etiqueta, mail.outbox[-1]))

        with translation.override(idioma):
            self._correos_del_pedido(capturar, idioma)
            self._correo_de_contrasena(capturar, idioma)
        self._correos_de_afiliados(capturar)
        return capturados

    def _variante_de_muestra(self):
        variante = (
            ProductVariant.objects.filter(is_active=True, inventory__quantity_available__gt=2)
            .select_related('product').first()
        )
        if variante:
            return variante
        producto = Product.objects.create(
            name='Camiseta de muestra', category=ProductCategory.objects.create(name='Muestra'),
            brand=Brand.objects.create(name='GoToGym muestra'), base_price=Decimal('189900'), stock=0,
        )
        variante = ProductVariant.objects.create(product=producto, sku='MUESTRA-001', size='M', color='negro')
        Inventory.objects.create(variant=variante, quantity_available=10)
        return variante

    def _usuario(self, correo, **campos):
        return get_user_model().objects.create_user(
            email=correo, username=correo, password=secrets.token_urlsafe(16), **campos,
        )

    def _correos_del_pedido(self, capturar, idioma):
        cliente = self._usuario('camila@example.com', first_name='Camila')
        variante = self._variante_de_muestra()
        pedido = create_order_from_cart(cliente, {str(variante.pk): 2}, DATOS_ENTREGA)
        pedido.language = idioma
        pedido.save(update_fields=['language'])

        capturar('Pedido recibido (pendiente de pago)', lambda: correos_pedido.pedido_recibido(pedido.pk))

        pedido.order_status = OrderStatus.CONFIRMED
        pedido.payment_status = PaymentStatus.APPROVED
        pedido.save(update_fields=['order_status', 'payment_status'])
        capturar('Pedido confirmado', lambda: correos_pedido.pedido_confirmado(pedido.pk))

        pedido.order_status = OrderStatus.SHIPPED
        pedido.save(update_fields=['order_status'])
        pedido.shipping_quote.tracking_code = 'GTG123456789CO'
        pedido.shipping_quote.save(update_fields=['tracking_code'])
        capturar('Pedido enviado', lambda: correos_pedido.pedido_enviado(pedido.pk))

        pedido.order_status = OrderStatus.CANCELLED
        capturar('Pedido cancelado (pago ya recibido)', lambda: correos_pedido.pedido_cancelado(pedido.pk))
        pedido.payment_status = PaymentStatus.CANCELLED
        pedido.save(update_fields=['order_status', 'payment_status'])
        capturar('Pedido cancelado (sin pago)', lambda: correos_pedido.pedido_cancelado(pedido.pk))
        self._pedido = pedido

    def _correo_de_contrasena(self, capturar, idioma):
        cliente = get_user_model().objects.get(email='camila@example.com')
        host = settings.SITIO_URL.split('://', 1)[-1]

        def pedir_enlace():
            # La vista real, con su plantilla y su limite de intentos.
            Client().post(
                reverse('password_reset'), {'email': cliente.email}, secure=True, HTTP_HOST=host,
            )

        with override_settings(ALLOWED_HOSTS=['*'], RATE_LIMIT_ENABLED=False):
            capturar('Restablecer contraseña', pedir_enlace)

    def _correos_de_afiliados(self, capturar):
        ahora = timezone.now()
        afiliado = self._usuario('afiliada@example.com', first_name='Valentina')
        perfil = PerfilAfiliado.objects.create(
            user=afiliado, status=EstadoAfiliado.APPROVED, referral_code='VALENTINA26',
            rejection_reason='No encontramos contenido de fitness en las redes indicadas.',
            exit_requested_at=ahora, exit_effective_at=ahora + timedelta(days=15),
            exit_reason=MotivoSalida.BREACH, exit_notes='Usó el código en sitios de cupones.',
        )
        Coupon.objects.create(
            code=perfil.referral_code, discount_type=CouponDiscountType.PERCENTAGE, value=Decimal('10'),
            afiliado=perfil, is_active=True,
        )
        pk = perfil.pk
        for etiqueta, accion in [
            ('Afiliados: solicitud recibida', lambda: correos_afiliados.solicitud_recibida(pk)),
            ('Afiliados: aprobado', lambda: correos_afiliados.afiliado_aprobado(pk)),
            ('Afiliados: rechazado', lambda: correos_afiliados.afiliado_rechazado(pk)),
            ('Afiliados: baja solicitada', lambda: correos_afiliados.baja_solicitada(pk)),
            ('Afiliados: baja efectiva', lambda: correos_afiliados.baja_efectiva(pk)),
            ('Afiliados: terminación', lambda: correos_afiliados.terminacion(pk)),
            ('Afiliados: cambio de comisión', lambda: correos_afiliados.cambio_de_tasa(pk, '12.50')),
            ('Afiliados: aviso general', lambda: correos_afiliados.aviso_general(
                pk, 'Actualizamos los términos del programa',
                'Publicamos una nueva versión de los términos.\nPuedes leerla desde tu panel.')),
        ]:
            capturar(etiqueta, accion)

        comision = Commission.objects.create(
            afiliado=perfil, order=self._pedido, amount=Decimal('24000'), status='pending',
            validation_ends_at=ahora + timedelta(days=10), extended_until=ahora + timedelta(days=25),
            extension_reason='Reclamo por posible fraude en revisión.',
        )
        capturar('Afiliados: validación extendida', lambda: correos_afiliados.validacion_extendida(comision.pk))

        solicitud = WithdrawalRequest.objects.create(
            afiliado=perfil, amount=Decimal('120000'), recovery_amount=Decimal('15000'),
            transaction_fee=Decimal('2000'), status=WithdrawalStatus.PAID,
        )
        capturar('Afiliados: comisión pagada', lambda: notify_commission_paid(solicitud.pk))

    # --- Salida -------------------------------------------------------------

    def _html(self, mensaje):
        for contenido, tipo in mensaje.alternatives:
            if tipo == 'text/html':
                return contenido
        raise CommandError(f'El correo "{mensaje.subject}" no trae versión HTML.')

    def _a_imagenes_locales(self, html):
        """Apunta las imagenes del sitio a los archivos del proyecto, para ver
        el HTML sin servidor."""
        sitio = settings.SITIO_URL
        estaticos = Path(settings.STATICFILES_DIRS[0]).resolve().as_uri() + '/'
        medios = Path(settings.MEDIA_ROOT).resolve().as_uri() + '/'
        return (
            html.replace(f'{sitio}{settings.STATIC_URL}', estaticos)
            .replace(f'{sitio}{settings.MEDIA_URL}', medios)
        )

    def _escribir(self, carpeta, capturados):
        carpeta.mkdir(parents=True, exist_ok=True)
        filas = []
        for numero, (etiqueta, mensaje) in enumerate(capturados, start=1):
            nombre = f'{numero:02d}.html'
            (carpeta / nombre).write_text(self._a_imagenes_locales(self._html(mensaje)), encoding='utf-8')
            (carpeta / f'{numero:02d}.txt').write_text(mensaje.body, encoding='utf-8')
            filas.append(
                f'<li><a href="{nombre}">{etiqueta}</a> &middot; <small>{mensaje.subject}</small> '
                f'&middot; <a href="{numero:02d}.txt">texto</a></li>'
            )
        indice = (
            '<!doctype html><meta charset="utf-8"><title>Vista previa de correos</title>'
            '<body style="font-family:Arial,sans-serif;max-width:720px;margin:32px auto;line-height:1.8">'
            '<h1>Vista previa de correos</h1><ol>' + ''.join(filas) + '</ol>'
        )
        (carpeta / 'index.html').write_text(indice, encoding='utf-8')

    def _enviar(self, capturados, destinatario, backend):
        conexion = get_connection(backend=backend)
        if not backend.endswith('smtp.EmailBackend'):
            self.stdout.write(self.style.WARNING(f'Backend activo: {backend}. Sin EMAIL_HOST no sale de este equipo.'))
        for _etiqueta, mensaje in capturados:
            mensaje.to = [destinatario]
            mensaje.subject = f'[Vista previa] {mensaje.subject}'
            mensaje.connection = conexion
            mensaje.send()
        self.stdout.write(self.style.SUCCESS(f'{len(capturados)} correos enviados a {destinatario}.'))
