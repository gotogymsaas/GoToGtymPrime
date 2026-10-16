"""Correos al cliente sobre su pedido.

Cada funcion es una tarea para `gotogym.tasks.enqueue`: vive a nivel de
modulo y recibe solo el id del pedido. Un fallo de correo nunca debe deshacer
la accion que lo origino (confirmar un pago, cambiar un estado), asi que se
deja en el log.

El correo sale en el idioma en que la persona hizo el pedido (`Order.language`),
no en el de quien dispare la tarea: un pago confirmado por el webhook de
Mercado Pago no tiene idioma de navegacion.
"""
import logging
from contextlib import contextmanager
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext

from .models import Order, PaymentStatus

logger = logging.getLogger(__name__)


def _firma():
    return gettext('Equipo GoToGym') + '\nsupport@gotogym.store\n'


def _pesos(valor):
    """1234567 -> $1.234.567 (formato colombiano, sin decimales)."""
    entero = int(Decimal(valor).quantize(Decimal('1')))
    return '$' + f'{entero:,}'.replace(',', '.')


def _pedido(order_id):
    return Order.objects.select_related('address', 'shipping_quote').prefetch_related('items').get(pk=order_id)


@contextmanager
def _en_el_idioma_del_pedido(pedido):
    with translation.override(pedido.language or 'es'):
        yield


def _enlace_del_pedido(pedido):
    return f'{settings.SITIO_URL}{reverse("orders:order_detail", args=[pedido.order_number])}'


def _saludo(pedido):
    nombre = pedido.address.full_name.split(' ')[0] if hasattr(pedido, 'address') and pedido.address.full_name else ''
    if nombre:
        return gettext('Hola %(nombre)s,') % {'nombre': nombre} + '\n\n'
    return gettext('Hola,') + '\n\n'


def _enviar(pedido, asunto, cuerpo):
    try:
        send_mail(subject=asunto, message=cuerpo, from_email=None, recipient_list=[pedido.email])
    except Exception:
        logger.exception('No se pudo enviar el correo "%s" del pedido %s', asunto, pedido.order_number)


def _resumen(pedido):
    lineas = [
        f'- {gettext(item.product_name_snapshot)} ({gettext(item.size_snapshot)}/{gettext(item.color_snapshot)}) '
        f'x{item.quantity}: {_pesos(item.line_total)}'
        for item in pedido.items.all()
    ]
    lineas.append('')
    lineas.append(f'{gettext("Subtotal")}: {_pesos(pedido.subtotal)}')
    if pedido.discount_total:
        lineas.append(f'{gettext("Descuento")}: -{_pesos(pedido.discount_total)}')
    lineas.append(f'{gettext("Envío")}: {_pesos(pedido.shipping_cost)}')
    lineas.append(f'{gettext("Total")}: {_pesos(pedido.total)}')
    return '\n'.join(lineas)


def pedido_confirmado(order_id):
    pedido = _pedido(order_id)
    with _en_el_idioma_del_pedido(pedido):
        direccion = pedido.address
        dias = getattr(getattr(pedido, 'shipping_quote', None), 'estimated_days', None)
        entrega = gettext('Tiempo estimado de entrega: unos %(dias)s días hábiles.') % {'dias': dias} + '\n' if dias else ''
        _enviar(
            pedido, gettext('Confirmamos tu pedido %(numero)s') % {'numero': pedido.order_number},
            f'{_saludo(pedido)}'
            + gettext('Recibimos tu pago y confirmamos tu pedido %(numero)s. Ya estamos preparándolo.') % {
                'numero': pedido.order_number} + '\n\n'
            f'{_resumen(pedido)}\n\n'
            + gettext('Se enviará a: %(direccion)s, %(ciudad)s, %(departamento)s.') % {
                'direccion': direccion.address_line, 'ciudad': direccion.city, 'departamento': direccion.department} + '\n'
            f'{entrega}\n'
            + gettext('Puedes ver el estado de tu pedido aquí: %(enlace)s') % {'enlace': _enlace_del_pedido(pedido)} + '\n\n'
            + gettext('Te avisaremos por este medio cuando salga de nuestras manos.') + '\n\n'
            f'{_firma()}',
        )


def _linea_de_guia(pedido):
    envio = getattr(pedido, 'shipping_quote', None)
    if not envio or not envio.tracking_code:
        return ''
    return gettext('Transportadora: %(transportadora)s · Guía: %(guia)s') % {
        'transportadora': envio.carrier_name, 'guia': envio.tracking_code} + '\n\n'


def pedido_enviado(order_id):
    pedido = _pedido(order_id)
    with _en_el_idioma_del_pedido(pedido):
        _enviar(
            pedido, gettext('Tu pedido %(numero)s va en camino') % {'numero': pedido.order_number},
            f'{_saludo(pedido)}'
            + gettext('Tu pedido %(numero)s salió y va en camino a %(ciudad)s.') % {
                'numero': pedido.order_number, 'ciudad': pedido.address.city} + '\n\n'
            f'{_linea_de_guia(pedido)}'
            + gettext('Puedes seguir su estado aquí: %(enlace)s') % {'enlace': _enlace_del_pedido(pedido)} + '\n\n'
            + gettext(
                'Al recibirlo, revisa que el empaque esté en buen estado. Si algo no está bien, '
                'escríbenos con tu número de pedido.'
            ) + '\n\n'
            f'{_firma()}',
        )


def pedido_cancelado(order_id):
    pedido = _pedido(order_id)
    with _en_el_idioma_del_pedido(pedido):
        if pedido.payment_status == PaymentStatus.APPROVED:
            explicacion = gettext(
                'No pudimos completar tu pedido, y tu pago ya había sido recibido. Nos pondremos en contacto '
                'contigo para devolverte el dinero por el mismo medio de pago.'
            )
        else:
            explicacion = gettext(
                'Tu pedido se canceló porque el pago no se completó a tiempo o porque lo cancelamos. '
                'No se hizo ningún cobro. Si quieres, puedes volver a hacer tu compra cuando quieras.'
            )
        _enviar(
            pedido, gettext('Tu pedido %(numero)s fue cancelado') % {'numero': pedido.order_number},
            f'{_saludo(pedido)}'
            f'{explicacion}\n\n'
            + gettext('Si tienes dudas, responde a este correo o escríbenos con tu número de pedido.') + '\n\n'
            f'{_firma()}',
        )
