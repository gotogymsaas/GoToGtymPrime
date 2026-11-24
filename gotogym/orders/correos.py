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
from django.utils import timezone, translation
from django.utils.formats import date_format
from django.utils.translation import gettext
from gotogym.correo import (
    Correo,
    aviso,
    boton,
    datos,
    dedicatoria,
    enviar_correo,
    parrafo,
    pasos,
    productos,
    tarjeta_regalo,
    totales,
    url_absoluta,
)
from tareas.idempotencia import efecto_unico
from tienda.templatetags.imagenes import url_imagen_producto

from . import tarjeta_pdf
from .models import GiftCard, Order, PaymentStatus

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
    if not nombre and pedido.user is not None:
        # La compra de una tarjeta de regalo no tiene direccion de entrega.
        nombre = (pedido.user.first_name or '').split(' ')[0]
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
    # El fallo se registra y se propaga: la tarea queda como fallida y el
    # trabajador la reintenta (con el backend `sync` lo captura quien la
    # ejecuta, igual que antes).
    try:
        enviar_correo(pedido.email, correo)
    except Exception:
        logger.exception('No se pudo enviar el correo "%s" del pedido %s', correo.asunto, pedido.order_number)
        raise


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
            'detalle': ' / '.join(gettext(v) for v in (item.size_snapshot, item.color_snapshot) if v),
            'cantidad': item.quantity,
            'total': _pesos(item.line_total),
            'imagen': _imagen_del_producto(item),
        }
        for item in pedido.items.all()
    ]
    filas = [(gettext('Subtotal'), _pesos(pedido.subtotal))]
    if pedido.discount_total:
        filas.append((gettext('Descuento'), f'-{_pesos(pedido.discount_total)}'))
    if not pedido.is_gift_card_purchase:
        filas.append((gettext('Envío'), _pesos(pedido.shipping_cost)))
    if pedido.gift_card_total:
        filas.append((gettext('Pagado con tarjeta de regalo'), f'-{_pesos(pedido.gift_card_total)}'))
    filas.append((gettext('Total a pagar') if pedido.gift_card_total else gettext('Total'), _pesos(pedido.total)))
    return [productos(lineas), totales(filas)]


def _boton_del_pedido(pedido, frase_con_enlace):
    """Boton "Ver mi pedido"; `frase_con_enlace` es la frase de la version de
    texto, que ya trae el enlace."""
    enlace = _enlace_del_pedido(pedido)
    return boton(gettext('Ver mi pedido'), enlace, texto_plano=frase_con_enlace % {'enlace': enlace})


@efecto_unico
def pedido_recibido(order_id):
    """Sale al crear el pedido, antes de que el pago se confirme: deja claro que
    esta pendiente y cuanto tiempo hay para pagarlo."""
    pedido = _pedido(order_id)
    with _en_el_idioma_del_pedido(pedido):
        bloques = [
            parrafo(gettext('Recibimos tu pedido %(numero)s y está pendiente de pago.') % {
                'numero': pedido.order_number}),
            *_resumen(pedido),
            *_aviso_de_envio_de_tarjeta(pedido),
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


@efecto_unico
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


@efecto_unico
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


@efecto_unico
def pedido_cancelado(order_id):
    pedido = _pedido(order_id)
    with _en_el_idioma_del_pedido(pedido):
        if pedido.payment_status == PaymentStatus.APPROVED and pedido.is_gift_card_purchase:
            explicacion = gettext(
                'Cancelamos la compra de tu tarjeta de regalo y la tarjeta quedó anulada. Te devolveremos el '
                'dinero por el mismo medio de pago.'
            )
        elif pedido.payment_status == PaymentStatus.APPROVED and pedido.total > 0:
            explicacion = gettext(
                'No pudimos completar tu pedido, y tu pago ya había sido recibido. Nos pondremos en contacto '
                'contigo para devolverte el dinero por el mismo medio de pago.'
            )
        elif pedido.payment_status == PaymentStatus.APPROVED:
            explicacion = gettext('No pudimos completar tu pedido.')
        else:
            explicacion = gettext(
                'Tu pedido se canceló porque el pago no se completó a tiempo o porque lo cancelamos. '
                'No se hizo ningún cobro. Si quieres, puedes volver a hacer tu compra cuando quieras.'
            )
        bloques = [parrafo(explicacion)]
        if pedido.gift_card_total:
            bloques.append(parrafo(gettext(
                'Lo que pagaste con tu tarjeta de regalo (%(monto)s) volvió a su saldo.'
            ) % {'monto': _pesos(pedido.gift_card_total)}))
        bloques.append(parrafo(gettext('Si tienes dudas, escríbenos a support@gotogym.store con tu número de pedido.')))
        _enviar(pedido, _correo(
            pedido, gettext('Tu pedido %(numero)s fue cancelado') % {'numero': pedido.order_number},
            gettext('Tu pedido fue cancelado'), bloques,
        ))


# ---------------------------------------------------------------- tarjetas de regalo

def _aviso_de_envio_de_tarjeta(pedido):
    tarjeta = getattr(pedido, 'purchased_gift_card', None) if pedido.is_gift_card_purchase else None
    if tarjeta is None:
        return []
    return [parrafo(gettext(
        'Cuando se apruebe el pago, enviaremos la tarjeta de regalo a %(nombre)s (%(correo)s).'
    ) % {'nombre': tarjeta.recipient_name, 'correo': tarjeta.recipient_email})]


def _fecha(momento):
    return date_format(timezone.localtime(momento), 'DATE_FORMAT')


def correo_tarjeta_regalo(tarjeta, con_pdf=False):
    """El correo de regalo que recibe el destinatario. Se arma aparte del envio
    para poder previsualizarlo (`previsualizar_correos`). `con_pdf` agrega la
    frase que avisa del PDF adjunto."""
    remitente = tarjeta.sender_name
    vence = _fecha(tarjeta.expires_at)
    bloques = [
        parrafo(gettext('%(remitente)s te regaló una tarjeta de GoToGym para que elijas lo que más te guste.') % {
            'remitente': remitente}),
        tarjeta_regalo(
            valor=_pesos(tarjeta.balance),
            codigo=tarjeta.display_code,
            etiqueta_codigo=gettext('Tu código'),
            vigencia=gettext('Válida hasta el %(fecha)s') % {'fecha': vence},
            encabezado=gettext('Tarjeta de regalo'),
        ),
    ]
    if tarjeta.message:
        bloques.append(dedicatoria(tarjeta.message, remitente))
    if con_pdf:
        bloques.append(parrafo(gettext(
            'Te adjuntamos la tarjeta en PDF, por si quieres imprimirla o guardarla.'
        )))
    bloques += [
        pasos(gettext('Cómo usarla'), [
            gettext('Elige tus prendas en la tienda de GoToGym.'),
            gettext('Inicia sesión o crea tu cuenta: la necesitas para pagar.'),
            gettext('En el pago, escribe el código en el campo "Cupón o tarjeta de regalo".'),
        ]),
        aviso(gettext(
            'Tu tarjeta vence el %(fecha)s. Puedes usarla en una o varias compras hasta esa fecha; usar una '
            'parte del saldo no amplía el plazo. Si el saldo no alcanza para tu compra, pagas la diferencia '
            'con otro medio. Al vencer, el saldo que quede ya no se podrá usar. No se cambia por dinero.'
        ) % {'fecha': vence}),
        boton(
            gettext('Ir a la tienda'), url_absoluta(reverse('tienda:producto_list')),
            texto_plano=gettext('Entra a la tienda: %(enlace)s') % {
                'enlace': url_absoluta(reverse('tienda:producto_list'))},
        ),
    ]
    return Correo(
        asunto=gettext('%(remitente)s te envió una tarjeta de regalo de GoToGym') % {'remitente': remitente},
        titulo=gettext('Tienes un regalo'),
        kicker=gettext('De parte de %(remitente)s') % {'remitente': remitente},
        saludo=gettext('Hola %(nombre)s,') % {'nombre': tarjeta.recipient_name},
        previa=gettext('%(remitente)s te regaló %(valor)s para tu próxima compra en GoToGym.') % {
            'remitente': remitente, 'valor': _pesos(tarjeta.balance)},
        bloques=bloques,
        pie=gettext(
            'Recibes este correo porque %(remitente)s te regaló una tarjeta de GoToGym. Si no conoces a '
            'quien te la envía, puedes ignorar este mensaje.'
        ) % {'remitente': remitente},
    )


def _pdf_adjunto(tarjeta):
    """El PDF de la tarjeta como adjunto, o ninguno si no se pudo generar: el
    correo con el codigo sale igual."""
    try:
        contenido = tarjeta_pdf.pdf_de_tarjeta(tarjeta)
    except Exception:
        logger.exception('No se pudo generar el PDF de la tarjeta de regalo %s', tarjeta.masked_code)
        return []
    nombre = gettext('Tarjeta-de-regalo-GoToGym') + '.pdf'
    return [(nombre, contenido, 'application/pdf')]


@efecto_unico
def tarjeta_regalo_para_destinatario(gift_card_id):
    """Envia la tarjeta a quien la recibe, en el idioma en que se compro.
    Registra el envio solo si salio bien, para que el panel muestre cuales
    hay que reenviar."""
    tarjeta = GiftCard.objects.filter(pk=gift_card_id).first()
    if tarjeta is None or tarjeta.expires_at is None:
        return
    with translation.override(tarjeta.language or 'es'):
        adjuntos = _pdf_adjunto(tarjeta)
        correo = correo_tarjeta_regalo(tarjeta, con_pdf=bool(adjuntos))
    try:
        enviar_correo(tarjeta.recipient_email, correo, adjuntos)
    except Exception:
        logger.exception('No se pudo enviar la tarjeta de regalo %s', tarjeta.masked_code)
        raise
    GiftCard.objects.filter(pk=tarjeta.pk).update(sent_at=timezone.now())


@efecto_unico
def tarjeta_regalo_comprada(order_id):
    """Confirmacion a quien compro la tarjeta. No lleva el codigo completo: el
    codigo es de quien recibe el regalo."""
    pedido = _pedido(order_id)
    tarjeta = getattr(pedido, 'purchased_gift_card', None)
    if tarjeta is None:
        return
    with _en_el_idioma_del_pedido(pedido):
        bloques = [
            parrafo(gettext(
                'Recibimos tu pago. Enviamos tu tarjeta de regalo a %(nombre)s, a su correo %(correo)s.'
            ) % {'nombre': tarjeta.recipient_name, 'correo': tarjeta.recipient_email}),
            datos([
                (gettext('Valor'), _pesos(tarjeta.initial_amount)),
                (gettext('Para'), tarjeta.recipient_name),
                (gettext('Tarjeta'), tarjeta.masked_code),
                (gettext('Válida hasta'), _fecha(tarjeta.expires_at)),
            ]),
            aviso(gettext(
                'Si el correo de destino tiene un error o tu regalo no llegó, escríbenos a support@gotogym.store '
                'con tu número de pedido y lo reenviamos.'
            )),
            parrafo(gettext(
                'Si te arrepientes de la compra, puedes pedir la devolución del dinero dentro de los 5 días '
                'hábiles siguientes, siempre que la tarjeta no se haya usado.'
            )),
            _boton_del_pedido(pedido, gettext('Puedes ver tu compra aquí: %(enlace)s')),
        ]
        _enviar(pedido, _correo(
            pedido, gettext('Tu tarjeta de regalo va en camino a %(nombre)s') % {'nombre': tarjeta.recipient_name},
            gettext('Tu regalo va en camino'), bloques,
        ))
