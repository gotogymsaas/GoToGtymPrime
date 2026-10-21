"""Facturacion electronica de pedidos pagados con Alegra.

`emitir_factura` es una tarea (ver gotogym/tasks.py): se encola al confirmar el
pago y recibe solo el id del pedido. Nunca propaga un fallo de Alegra: lo deja
registrado en `Invoice` (estado `failed`, intentos y ultimo error) y el comando
`emitir_facturas_pendientes` lo reintenta. Un pago aprobado no depende de que
Alegra este disponible.

Los importes se recalculan desde el pedido, que es la fuente de verdad. Alegra
espera el precio de cada linea sin impuestos y el descuento como porcentaje,
asi que aqui se convierte: si los precios de la tienda ya incluyen IVA se
descuenta, y el descuento del cupon (que es del pedido completo) se reparte
como el mismo porcentaje en todas las lineas, sin tocar el envio.
"""
import logging
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from integrations.alegra.alegra_client import AlegraClient, AlegraError

from .models import DocumentType, Invoice, InvoiceStatus, Order, OrderStatus, PaymentStatus

logger = logging.getLogger(__name__)

# Intentos maximos que reintenta el comando; pasado esto la factura queda
# fallida a la espera de que alguien la revise.
MAX_INTENTOS = 5
# Una factura "en proceso" mas vieja que esto se da por abandonada (el proceso
# murio a mitad) y se puede volver a reclamar.
MINUTOS_EN_PROCESO = 10

REFERENCIA_ENVIO = 'ENVIO'
CENTAVOS = Decimal('0.01')
PRECIO = Decimal('0.0001')
PORCENTAJE = Decimal('0.000001')

# Tipos de documento de la tienda -> tipos de identificacion de Alegra. Alegra
# no tiene PPT; el PEP es el mas cercano.
TIPO_DOCUMENTO_ALEGRA = {
    DocumentType.CC: 'CC',
    DocumentType.CE: 'CE',
    DocumentType.NIT: 'NIT',
    DocumentType.PA: 'PP',
    DocumentType.PPT: 'PEP',
    DocumentType.PEP: 'PEP',
}

# `payment_type_id` de Mercado Pago -> medio de pago DIAN de Alegra. Un tipo que
# no esta aqui (por ejemplo dinero en cuenta) usa `ALEGRA_MEDIO_DE_PAGO`.
MEDIO_DE_PAGO_MERCADO_PAGO = {
    'credit_card': 'CREDIT_CARD',
    'debit_card': 'DEBIT_CARD',
    'prepaid_card': 'DEBIT_CARD',
    'bank_transfer': 'DEBIT_TRANSFER',
    'ticket': 'CASH',
    'atm': 'CASH',
}

_PESOS_DV = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


class FacturacionError(Exception):
    """El pedido no se puede facturar tal como esta (datos que faltan)."""


def facturacion_activa():
    return bool(
        getattr(settings, 'ALEGRA_FACTURACION_ACTIVA', False)
        and getattr(settings, 'ALEGRA_EMAIL', '')
        and getattr(settings, 'ALEGRA_API_TOKEN', '')
    )


def digito_verificacion(nit):
    """Digito de verificacion de un NIT colombiano (algoritmo de la DIAN)."""
    digitos = [int(c) for c in str(nit) if c.isdigit()]
    if not digitos or len(digitos) > len(_PESOS_DV):
        raise FacturacionError('NIT inválido: no se puede calcular el dígito de verificación.')
    suma = sum(d * p for d, p in zip(reversed(digitos), _PESOS_DV, strict=False))
    resto = suma % 11
    return resto if resto < 2 else 11 - resto


def _iva_porcentaje():
    if not getattr(settings, 'ALEGRA_IVA_TAX_ID', ''):
        return Decimal('0')
    return Decimal(str(getattr(settings, 'ALEGRA_IVA_PORCENTAJE', '19')))


def _precio_sin_iva(precio):
    """Precio que se envia a Alegra: sin impuestos."""
    porcentaje = _iva_porcentaje()
    if porcentaje and getattr(settings, 'ALEGRA_PRECIOS_INCLUYEN_IVA', True):
        precio = precio / (1 + porcentaje / 100)
    return precio.quantize(PRECIO, rounding=ROUND_HALF_UP)


def _impuestos():
    iva_id = getattr(settings, 'ALEGRA_IVA_TAX_ID', '')
    return [{'id': str(iva_id)}] if iva_id else []


def _numero(valor):
    return float(valor)


def facturable(order):
    """Solo se factura un pedido pagado y vigente. Uno cancelado (por ejemplo,
    por falta de stock aunque el pago se aprobara) se devuelve, no se factura."""
    return (
        order.payment_status == PaymentStatus.APPROVED
        and order.order_status not in (OrderStatus.CANCELLED, OrderStatus.PENDING_PAYMENT)
    )


def documento_de(order):
    """`(tipo, numero)` con que se factura: el del pedido y, si el comprador no
    lo escribio, el de su cuenta. Vacios si no hay ninguno."""
    if order.customer_document_number:
        return order.customer_document_type, order.customer_document_number
    usuario = order.user
    if usuario is not None and usuario.document_number:
        return usuario.document_type, usuario.document_number
    return '', ''


def pago_aprobado(order):
    """Transaccion de pago aprobada del pedido. Se lee por la relacion inversa:
    `orders` no puede importar `payments`."""
    return order.payment_transactions.filter(status='approved').order_by('-updated_at').first()


def medio_de_pago(pago):
    """Medio de pago DIAN de la factura, segun como pago el comprador."""
    tipo = ((pago.raw_payload or {}).get('payment') or {}).get('payment_type_id') if pago else None
    return MEDIO_DE_PAGO_MERCADO_PAGO.get(
        tipo, getattr(settings, 'ALEGRA_MEDIO_DE_PAGO', 'INSTRUMENT_NOT_DEFINED'),
    )


def _observaciones(order, pago):
    texto = f'Pedido {order.order_number}.'
    if pago is not None and pago.provider == 'mercadopago':
        texto += f' Pagado con Mercado Pago (pago {pago.payment_id}).'
    return texto


def armar_contacto(order):
    """Cuerpo para crear al comprador como cliente en Alegra."""
    direccion = getattr(order, 'address', None)
    nombre = (direccion.full_name if direccion else '').strip() or order.email
    tipo_documento, numero = documento_de(order)
    tipo = TIPO_DOCUMENTO_ALEGRA[tipo_documento]
    identificacion = {'type': tipo, 'number': numero}
    es_empresa = tipo == 'NIT'
    if es_empresa:
        identificacion['dv'] = str(digito_verificacion(numero))

    contacto = {
        'identificationObject': identificacion,
        'kindOfPerson': 'LEGAL_ENTITY' if es_empresa else 'PERSON_ENTITY',
        'regime': 'COMMON_REGIME' if es_empresa else 'SIMPLIFIED_REGIME',
        'email': order.email,
        'phonePrimary': order.phone,
        'type': ['client'],
    }
    if es_empresa:
        contacto['name'] = nombre
    else:
        partes = nombre.split()
        contacto['nameObject'] = {
            'firstName': partes[0],
            'lastName': ' '.join(partes[1:]) or partes[0],
        }
    if direccion:
        contacto['address'] = {
            'address': ' '.join(filter(None, [direccion.address_line, direccion.address_complement])),
            'city': direccion.city,
            'department': direccion.department,
        }
    return contacto


def _datos_de_producto(linea):
    nombre = linea.product_name_snapshot
    detalle = ' / '.join(filter(None, [linea.size_snapshot, linea.color_snapshot]))
    return f'{nombre} - {detalle}' if detalle else nombre


def armar_factura(order, contacto_id, ids_de_items, hoy=None, pago=None):
    """Cuerpo de `POST /invoices` para un pedido.

    `ids_de_items` mapea la referencia de cada linea (el SKU, o `ENVIO`) al id
    del producto en Alegra.
    """
    hoy = hoy or timezone.localdate()
    descuento_pct = Decimal('0')
    if order.subtotal and order.discount_total:
        descuento_pct = (order.discount_total / order.subtotal * 100).quantize(
            PORCENTAJE, rounding=ROUND_HALF_UP,
        )

    items = []
    for linea in order.items.all():
        items.append({
            'id': ids_de_items[linea.sku_snapshot],
            'description': _datos_de_producto(linea),
            'reference': linea.sku_snapshot,
            'price': _numero(_precio_sin_iva(linea.unit_price_snapshot)),
            'quantity': linea.quantity,
            'discount': _numero(descuento_pct),
            'tax': _impuestos(),
        })
    if order.shipping_cost > 0:
        items.append({
            'id': ids_de_items[REFERENCIA_ENVIO],
            'description': 'Envío',
            'reference': REFERENCIA_ENVIO,
            'price': _numero(_precio_sin_iva(order.shipping_cost)),
            'quantity': 1,
            'discount': 0,
            'tax': _impuestos(),
        })

    cuerpo = {
        'date': hoy.isoformat(),
        'dueDate': hoy.isoformat(),
        'client': str(contacto_id),
        'items': items,
        'status': 'open',
        'paymentForm': 'CASH',
        'paymentMethod': medio_de_pago(pago),
        'type': 'NATIONAL',
        'operationType': 'STANDARD',
        # Permite cruzar la factura de Alegra con el pedido de la tienda. Las
        # observaciones son internas: no salen en el PDF del cliente.
        'purchaseOrderNumber': order.order_number,
        'observations': _observaciones(order, pago),
    }
    plantilla = getattr(settings, 'ALEGRA_NUMBER_TEMPLATE_ID', '')
    if plantilla:
        cuerpo['numberTemplate'] = {'id': str(plantilla)}
    if getattr(settings, 'ALEGRA_EMITIR_ELECTRONICA', True):
        cuerpo['stamp'] = {'generateStamp': True}
    return cuerpo


def _resolver_contacto(cliente, order):
    tipo_documento, numero = documento_de(order)
    if not numero:
        consumidor_final = getattr(settings, 'ALEGRA_CONSUMIDOR_FINAL_ID', '')
        if consumidor_final:
            return str(consumidor_final)
        raise FacturacionError('El pedido no tiene documento del comprador.')
    if tipo_documento not in TIPO_DOCUMENTO_ALEGRA:
        raise FacturacionError('El pedido tiene un tipo de documento desconocido.')

    contacto = armar_contacto(order)
    dv = contacto['identificationObject'].get('dv', '')
    existente = cliente.find_contact(numero, dv=dv)
    if existente:
        return str(existente['id'])
    return str(cliente.create_contact(contacto)['id'])


def _resolver_item(cliente, referencia, cuerpo):
    existente = cliente.find_item(referencia)
    if existente:
        return str(existente['id'])
    return str(cliente.create_item(cuerpo)['id'])


def _resolver_items(cliente, order):
    generico = getattr(settings, 'ALEGRA_ITEM_GENERICO_ID', '')
    ids = {}
    for linea in order.items.all():
        referencia = linea.sku_snapshot
        if referencia in ids:
            continue
        if generico:
            ids[referencia] = str(generico)
            continue
        ids[referencia] = _resolver_item(cliente, referencia, {
            'name': _datos_de_producto(linea)[:150],
            'reference': referencia[:45],
            'price': _numero(_precio_sin_iva(linea.unit_price_snapshot)),
            'tax': _impuestos(),
            'type': 'product',
        })
    if order.shipping_cost > 0:
        if generico:
            ids[REFERENCIA_ENVIO] = str(generico)
        else:
            ids[REFERENCIA_ENVIO] = _resolver_item(cliente, REFERENCIA_ENVIO, {
                'name': 'Envío',
                'reference': REFERENCIA_ENVIO,
                'price': _numero(_precio_sin_iva(order.shipping_cost)),
                'tax': _impuestos(),
                'type': 'service',
            })
    return ids


def _numero_de_factura(respuesta):
    plantilla = respuesta.get('numberTemplate')
    if isinstance(plantilla, list):
        plantilla = plantilla[0] if plantilla else None
    if isinstance(plantilla, dict):
        completo = plantilla.get('fullNumber')
        if completo:
            return str(completo)
        if plantilla.get('number'):
            return f"{plantilla.get('prefix') or ''}{plantilla['number']}"
    return str(respuesta.get('number') or '')


def _reclamar(factura):
    """Pasa la factura a `processing` si nadie mas la esta emitiendo.

    El UPDATE condicional es atomico: de dos avisos de pago simultaneos solo
    uno lo gana y emite, el otro sale sin llamar a Alegra.
    """
    ahora = timezone.now()
    abandonada = ahora - timedelta(minutes=MINUTOS_EN_PROCESO)
    reclamadas = Invoice.objects.filter(pk=factura.pk).filter(
        Q(status__in=[InvoiceStatus.PENDING, InvoiceStatus.FAILED])
        | Q(status=InvoiceStatus.PROCESSING, last_attempt_at__lt=abandonada)
    ).update(
        status=InvoiceStatus.PROCESSING, last_attempt_at=ahora, attempts=F('attempts') + 1,
    )
    return reclamadas == 1


def _borrador_de(error):
    """Id del borrador que Alegra deja creado cuando la emision falla."""
    payload = error.payload if isinstance(error, AlegraError) else None
    if isinstance(payload, dict) and isinstance(payload.get('invoice'), dict):
        return str(payload['invoice'].get('id') or '')
    return ''


def _registrar_fallo(factura, error):
    mensaje = str(error) if isinstance(error, (AlegraError, FacturacionError)) else (
        f'Error inesperado ({type(error).__name__})'
    )
    if not isinstance(error, (AlegraError, FacturacionError)):
        logger.exception('Fallo inesperado al facturar el pedido %s', factura.order_id)
    else:
        logger.warning('No se pudo facturar el pedido %s: %s', factura.order_id, mensaje)
    campos = {'status': InvoiceStatus.FAILED, 'last_error': mensaje[:1000]}
    borrador = _borrador_de(error)
    if borrador:
        campos['alegra_invoice_id'] = borrador
    Invoice.objects.filter(pk=factura.pk).update(**campos)


def _borrar_borrador(cliente, factura):
    """Un intento anterior dejo un borrador en Alegra: se borra antes de
    reintentar para no duplicar la factura. Si ya no existe, da igual."""
    try:
        cliente.delete_invoice(factura.alegra_invoice_id)
    except AlegraError as error:
        if error.status != 404:
            raise
    Invoice.objects.filter(pk=factura.pk).update(alegra_invoice_id='')


def emitir_factura(order_id):
    """Emite la factura del pedido en Alegra. Idempotente y sin excepciones
    hacia afuera. Devuelve el estado final, o None si no habia nada que hacer.
    """
    if not facturacion_activa():
        return None

    order = Order.objects.select_related('address', 'user').filter(pk=order_id).first()
    if order is None or not facturable(order):
        return None

    try:
        with transaction.atomic():
            factura, _ = Invoice.objects.get_or_create(order=order)
    except IntegrityError:
        factura = Invoice.objects.get(order=order)

    if not _reclamar(factura):
        return None
    factura.refresh_from_db()

    try:
        if order.currency != 'COP':
            raise FacturacionError(f'Solo se factura en COP (el pedido está en {order.currency}).')
        cliente = AlegraClient.from_settings()
        if factura.alegra_invoice_id:
            _borrar_borrador(cliente, factura)
        contacto_id = _resolver_contacto(cliente, order)
        ids = _resolver_items(cliente, order)
        respuesta = cliente.create_invoice(
            armar_factura(order, contacto_id, ids, pago=pago_aprobado(order)),
        )
    except Exception as error:
        _registrar_fallo(factura, error)
        return InvoiceStatus.FAILED

    stamp = respuesta.get('stamp') if isinstance(respuesta.get('stamp'), dict) else {}
    Invoice.objects.filter(pk=factura.pk).update(
        status=InvoiceStatus.ISSUED,
        alegra_contact_id=contacto_id,
        alegra_invoice_id=str(respuesta.get('id', '')),
        number=_numero_de_factura(respuesta)[:60],
        cufe=str(stamp.get('cufe') or '')[:200],
        raw_response=respuesta,
        last_error='',
        issued_at=timezone.now(),
    )
    return InvoiceStatus.ISSUED


def ordenes_por_facturar(limite=50):
    """Ids de pedidos cuya factura esta por emitir o reintentarse.

    Siempre incluye las facturas ya intentadas (pendientes, fallidas con
    intentos disponibles o abandonadas en proceso). Los pedidos pagados que
    nunca tuvieron factura solo entran con `ALEGRA_FACTURAR_DESDE`, para que
    activar la integracion no facture de golpe el historico.
    """
    abandonada = timezone.now() - timedelta(minutes=MINUTOS_EN_PROCESO)
    condicion = (
        Q(invoice__status=InvoiceStatus.PENDING)
        | Q(invoice__status=InvoiceStatus.FAILED, invoice__attempts__lt=MAX_INTENTOS)
        | Q(invoice__status=InvoiceStatus.PROCESSING, invoice__last_attempt_at__lt=abandonada)
    )
    desde = getattr(settings, 'ALEGRA_FACTURAR_DESDE', '')
    if desde:
        inicio = timezone.make_aware(datetime.combine(date.fromisoformat(desde), time.min))
        condicion |= Q(invoice__isnull=True, paid_at__gte=inicio)
    pedidos = (
        Order.objects.filter(payment_status=PaymentStatus.APPROVED)
        .exclude(order_status__in=[OrderStatus.CANCELLED, OrderStatus.PENDING_PAYMENT])
        .filter(condicion)
        .order_by('paid_at', 'id')
    )
    return list(pedidos.values_list('pk', flat=True)[:limite])
