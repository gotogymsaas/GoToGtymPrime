"""Correos al cliente sobre su pedido.

Cada funcion es una tarea para `gotogym.tasks.enqueue`: vive a nivel de
modulo y recibe solo el id del pedido. Un fallo de correo nunca debe deshacer
la accion que lo origino (confirmar un pago, cambiar un estado), asi que se
deja en el log.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from .models import Order, PaymentStatus

logger = logging.getLogger(__name__)

FIRMA = 'Equipo GoToGym\nsupport@gotogym.store\n'


def _pesos(valor):
    """1234567 -> $1.234.567 (formato colombiano, sin decimales)."""
    entero = int(Decimal(valor).quantize(Decimal('1')))
    return '$' + f'{entero:,}'.replace(',', '.')


def _pedido(order_id):
    return Order.objects.select_related('address', 'shipping_quote').prefetch_related('items').get(pk=order_id)


def _enlace_del_pedido(pedido):
    return f'{settings.SITIO_URL}{reverse("orders:order_detail", args=[pedido.order_number])}'


def _saludo(pedido):
    nombre = pedido.address.full_name.split(' ')[0] if hasattr(pedido, 'address') and pedido.address.full_name else ''
    return f'Hola {nombre},\n\n' if nombre else 'Hola,\n\n'


def _enviar(pedido, asunto, cuerpo):
    try:
        send_mail(subject=asunto, message=cuerpo, from_email=None, recipient_list=[pedido.email])
    except Exception:
        logger.exception('No se pudo enviar el correo "%s" del pedido %s', asunto, pedido.order_number)


def _resumen(pedido):
    lineas = [
        f'- {item.product_name_snapshot} ({item.size_snapshot}/{item.color_snapshot}) x{item.quantity}: '
        f'{_pesos(item.line_total)}'
        for item in pedido.items.all()
    ]
    lineas.append('')
    lineas.append(f'Subtotal: {_pesos(pedido.subtotal)}')
    if pedido.discount_total:
        lineas.append(f'Descuento: -{_pesos(pedido.discount_total)}')
    lineas.append(f'Envío: {_pesos(pedido.shipping_cost)}')
    lineas.append(f'Total: {_pesos(pedido.total)}')
    return '\n'.join(lineas)


def pedido_confirmado(order_id):
    pedido = _pedido(order_id)
    direccion = pedido.address
    dias = getattr(getattr(pedido, 'shipping_quote', None), 'estimated_days', None)
    entrega = f'Tiempo estimado de entrega: unos {dias} días hábiles.\n' if dias else ''
    _enviar(
        pedido, f'Confirmamos tu pedido {pedido.order_number}',
        f'{_saludo(pedido)}'
        f'Recibimos tu pago y confirmamos tu pedido {pedido.order_number}. Ya estamos preparándolo.\n\n'
        f'{_resumen(pedido)}\n\n'
        f'Se enviará a: {direccion.address_line}, {direccion.city}, {direccion.department}.\n'
        f'{entrega}\n'
        f'Puedes ver el estado de tu pedido aquí: {_enlace_del_pedido(pedido)}\n\n'
        'Te avisaremos por este medio cuando salga de nuestras manos.\n\n'
        f'{FIRMA}',
    )


def pedido_enviado(order_id):
    pedido = _pedido(order_id)
    _enviar(
        pedido, f'Tu pedido {pedido.order_number} va en camino',
        f'{_saludo(pedido)}'
        f'Tu pedido {pedido.order_number} salió y va en camino a {pedido.address.city}.\n\n'
        f'Puedes seguir su estado aquí: {_enlace_del_pedido(pedido)}\n\n'
        'Al recibirlo, revisa que el empaque esté en buen estado. Si algo no está bien, '
        'escríbenos con tu número de pedido.\n\n'
        f'{FIRMA}',
    )


def pedido_cancelado(order_id):
    pedido = _pedido(order_id)
    if pedido.payment_status == PaymentStatus.APPROVED:
        explicacion = (
            'No pudimos completar tu pedido, y tu pago ya había sido recibido. Nos pondremos en contacto '
            'contigo para devolverte el dinero por el mismo medio de pago.'
        )
    else:
        explicacion = (
            'Tu pedido se canceló porque el pago no se completó a tiempo o porque lo cancelamos. '
            'No se hizo ningún cobro. Si quieres, puedes volver a hacer tu compra cuando quieras.'
        )
    _enviar(
        pedido, f'Tu pedido {pedido.order_number} fue cancelado',
        f'{_saludo(pedido)}'
        f'{explicacion}\n\n'
        'Si tienes dudas, responde a este correo o escríbenos con tu número de pedido.\n\n'
        f'{FIRMA}',
    )
