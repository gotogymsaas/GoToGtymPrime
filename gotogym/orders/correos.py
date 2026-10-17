"""Correos al cliente sobre su pedido.

Cada funcion es una tarea para `gotogym.tasks.enqueue`: vive a nivel de
modulo y recibe solo el id del pedido. Un fallo de correo nunca debe deshacer
la accion que lo origino (confirmar un pago, cambiar un estado), asi que se
deja en el log.

El correo sale en el idioma en que la persona hizo el pedido (`Order.language`),
no en el de quien dispare la tarea: un pago confirmado por el webhook de
Mercado Pago no tiene idioma de navegacion.

Cada correo se escribe como contenido (`gotogym.correo`) y sale como HTML de
marca con su version de texto.
"""
import logging
from contextlib import contextmanager
from decimal import Decimal

from django.conf import settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext
from gotogym.correo import (
    Correo,
    aviso,
    boton,
    datos,
    enviar_correo,
    parrafo,
    productos,
    totales,
    url_absoluta,
)
from tienda.templatetags.imagenes import url_imagen_producto

from .models import Order, PaymentStatus

logger = logging.getLogger(__name__)


def _pesos(valor):
    """1234567 -> $1.234.567 (formato colombiano, sin decimales)."""
    entero = int(Decimal(valor).quantize(Decimal('1')))
    return '$' + f'{entero:,}'.replace(',', '.')


def _pedido(order_id):
    return (
        Order.objects.select_related('address', 'shipping_quote')
        .prefetch_related('items__variant__product__media')
        .get(pk=order_id)
    )


@contextmanager
def _en_el_idioma_del_pedido(pedido):
    with translation.override(pedido.language or 'es'):
        yield


def _enlace_del_pedido(pedido):
    return f'{settings.SITIO_URL}{reverse("orders:order_detail", args=[pedido.order_number])}'


def _saludo(pedido):
    nombre = pedido.address.full_name.split(' ')[0] if hasattr(pedido, 'address') and pedido.address.full_name else ''
    if nombre:
        return gettext('Hola %(nombre)s,') % {'nombre': nombre}
    return gettext('Hola,')


def _correo(pedido, asunto, titulo, bloques):
    return Correo(
        asunto=asunto, titulo=titulo, bloques=bloques,
        kicker=f'{gettext("Pedido")} {pedido.order_number}',
        saludo=_saludo(pedido),
        pie=gettext('Recibes este correo porque hiciste un pedido en GoToGym.'),
    )


def _enviar(pedido, correo):
    try:
        enviar_correo(pedido.email, correo)
    except Exception:
        logger.exception('No se pudo enviar el correo "%s" del pedido %s', correo.asunto, pedido.order_number)


def _imagen_del_producto(item):
    """Direccion publica de la foto del producto; vacia si no la tiene, si el
    producto ya no existe o si no se puede resolver (el correo sale igual)."""
    variante = item.variant
    if variante is None:
        return ''
    try:
        imagen = variante.product.primary_image
        if not imagen:
            return ''
        return url_absoluta(url_imagen_producto(imagen.name))
    except Exception:
        logger.warning('No se pudo resolver la foto de %s para el correo', item.sku_snapshot, exc_info=True)
        return ''


def _resumen(pedido):
    lineas = [
        {
            'nombre': gettext(item.product_name_snapshot),
            'detalle': f'{gettext(item.size_snapshot)} / {gettext(item.color_snapshot)}',
            'cantidad': item.quantity,
            'total': _pesos(item.line_total),
            'imagen': _imagen_del_producto(item),
        }
        for item in pedido.items.all()
    ]
    filas = [(gettext('Subtotal'), _pesos(pedido.subtotal))]
    if pedido.discount_total:
        filas.append((gettext('Descuento'), f'-{_pesos(pedido.discount_total)}'))
    filas.append((gettext('Envío'), _pesos(pedido.shipping_cost)))
    filas.append((gettext('Total'), _pesos(pedido.total)))
    return [productos(lineas), totales(filas)]


def _boton_del_pedido(pedido, frase_con_enlace):
    """Boton "Ver mi pedido"; `frase_con_enlace` es la frase de la version de
    texto, que ya trae el enlace."""
    enlace = _enlace_del_pedido(pedido)
    return boton(gettext('Ver mi pedido'), enlace, texto_plano=frase_con_enlace % {'enlace': enlace})


def pedido_recibido(order_id):
    """Sale al crear el pedido, antes de que el pago se confirme: deja claro que
    esta pendiente y cuanto tiempo hay para pagarlo."""
    pedido = _pedido(order_id)
    with _en_el_idioma_del_pedido(pedido):
        bloques = [
            parrafo(gettext('Recibimos tu pedido %(numero)s y está pendiente de pago.') % {
                'numero': pedido.order_number}),
            *_resumen(pedido),
            parrafo(gettext('Si ya pagaste, te enviaremos la confirmación en cuanto se acredite el pago.')),
            aviso(gettext(
                'Si el pago no se completa en %(horas)s horas, el pedido se cancelará automáticamente '
                'y no se hará ningún cobro.'
            ) % {'horas': settings.ORDER_PAYMENT_WINDOW_HOURS}),
            _boton_del_pedido(pedido, gettext('Puedes ver el estado de tu pedido aquí: %(enlace)s')),
        ]
        _enviar(pedido, _correo(
            pedido, gettext('Recibimos tu pedido %(numero)s') % {'numero': pedido.order_number},
            gettext('Recibimos tu pedido'), bloques,
        ))


def pedido_confirmado(order_id):
    pedido = _pedido(order_id)
    with _en_el_idioma_del_pedido(pedido):
        direccion = pedido.address
        dias = getattr(getattr(pedido, 'shipping_quote', None), 'estimated_days', None)
        bloques = [
            parrafo(gettext('Recibimos tu pago y confirmamos tu pedido %(numero)s. Ya estamos preparándolo.') % {
                'numero': pedido.order_number}),
            *_resumen(pedido),
            parrafo(gettext('Se enviará a: %(direccion)s, %(ciudad)s, %(departamento)s.') % {
                'direccion': direccion.address_line, 'ciudad': direccion.city, 'departamento': direccion.department}),
        ]
        if dias:
            bloques.append(parrafo(gettext('Tiempo estimado de entrega: unos %(dias)s días hábiles.') % {'dias': dias}))
        bloques += [
            parrafo(gettext('Te avisaremos por este medio cuando salga de nuestras manos.')),
            _boton_del_pedido(pedido, gettext('Puedes ver el estado de tu pedido aquí: %(enlace)s')),
        ]
        _enviar(pedido, _correo(
            pedido, gettext('Confirmamos tu pedido %(numero)s') % {'numero': pedido.order_number},
            gettext('Tu pedido está confirmado'), bloques,
        ))


def _datos_de_la_guia(pedido):
    envio = getattr(pedido, 'shipping_quote', None)
    if not envio or not envio.tracking_code:
        return []
    return [datos([
        (gettext('Transportadora'), envio.carrier_name),
        (gettext('Guía de envío'), envio.tracking_code),
    ])]


def pedido_enviado(order_id):
    pedido = _pedido(order_id)
    with _en_el_idioma_del_pedido(pedido):
        bloques = [
            parrafo(gettext('Tu pedido %(numero)s salió y va en camino a %(ciudad)s.') % {
                'numero': pedido.order_number, 'ciudad': pedido.address.city}),
            *_datos_de_la_guia(pedido),
            parrafo(gettext(
                'Al recibirlo, revisa que el empaque esté en buen estado. Si algo no está bien, '
                'escríbenos con tu número de pedido.'
            )),
            _boton_del_pedido(pedido, gettext('Puedes seguir su estado aquí: %(enlace)s')),
        ]
        _enviar(pedido, _correo(
            pedido, gettext('Tu pedido %(numero)s va en camino') % {'numero': pedido.order_number},
            gettext('Tu pedido va en camino'), bloques,
        ))


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
        bloques = [
            parrafo(explicacion),
            parrafo(gettext('Si tienes dudas, escríbenos a support@gotogym.store con tu número de pedido.')),
        ]
        _enviar(pedido, _correo(
            pedido, gettext('Tu pedido %(numero)s fue cancelado') % {'numero': pedido.order_number},
            gettext('Tu pedido fue cancelado'), bloques,
        ))
