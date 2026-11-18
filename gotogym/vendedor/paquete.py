"""Armado de la solicitud que la tienda envia al Coach.

Todo sale del servidor: el carrito de la sesion, los precios de
`ProductVariant`, las existencias de inventario y los indicadores de la
tienda. Del navegador solo se toma el texto del mensaje (que el visitante
escribe) y la pagina desde la que escribe, que se vuelve a resolver aqui y
solo sirve para saber que producto mira: nada de lo que el cliente declare
puede cambiar un precio, una existencia o una politica.

No se incluye ningun dato personal. El sujeto es un seudonimo derivado con la
clave del servidor y distinto del identificador de analitica, para no darle a
un tercero la llave con la que se cruzan los eventos de medicion.
"""
import hashlib
import time
import uuid
from urllib.parse import parse_qs, urlsplit

from analitica.services import hash_visitante
from carrito.services import (
    CART_VERSION,
    SESSION_CART_KEY,
    SESSION_VERSION_KEY,
    build_cart_context,
)
from django.conf import settings
from django.urls import Resolver404, resolve
from django.utils import timezone
from django.utils.translation import get_language
from gotogym.ajustes_tienda import compras_pausadas, pagos_habilitados
from inventory.services import get_available_quantity
from products import atributos

from . import contrato, evidencia, identidad, talla
from .models import CommerceMemoryItem, CommercePersonalizationConsent

MAX_LARGO_FILTRO = 100


def idioma_del_visitante():
    """`en` si el sitio esta en ingles; cualquier otro idioma se atiende en
    espanol (el portugues es parcial y no tiene selector)."""
    return 'en' if (get_language() or 'es').startswith('en') else 'es'


def sujeto_del_visitante(request):
    """`(sujeto, autenticado)`. Un seudonimo estable, no reversible y sin
    relacion con el correo ni con el identificador de analitica."""
    if request.user.is_authenticated:
        semilla = f'{settings.SECRET_KEY}:vendedor-usuario:{request.user.pk}'
        return f'shop_u_{hashlib.sha256(semilla.encode()).hexdigest()[:32]}', True
    semilla = f'{settings.SECRET_KEY}:vendedor-visitante:{hash_visitante(request)}'
    return f'shop_v_{hashlib.sha256(semilla.encode()).hexdigest()[:32]}', False


def contexto_de_pagina(request):
    """Pagina desde la que escribe el visitante, para saber que producto mira.

    Se toma de la cabecera `Referer` y se vuelve a resolver contra las rutas
    del sitio: solo cuenta si es de este mismo sitio. Es una pista para elegir
    candidatos, no un dato en el que se confie para nada mas."""
    vacio = {'url_name': '', 'product_id': None, 'variant_id': None, 'filtro': ''}
    origen = request.META.get('HTTP_REFERER', '')
    if not origen:
        return vacio
    partes = urlsplit(origen)
    if partes.netloc and partes.netloc != request.get_host():
        return vacio
    try:
        ruta = resolve(partes.path)
    except Resolver404:
        return vacio
    nombre = f'{ruta.namespace}:{ruta.url_name}' if ruta.namespace else (ruta.url_name or '')
    producto = ruta.kwargs.get('pk') if nombre == 'tienda:producto_detail' else None
    filtro = parse_qs(partes.query).get('filtro', [''])[0].strip()[:MAX_LARGO_FILTRO]
    return {
        'url_name': nombre[:80],
        'product_id': producto if isinstance(producto, int) else None,
        'variant_id': None,
        'filtro': filtro,
    }


def carrito_de_la_sesion(request):
    """`(carrito, ids_de_producto)` del visitante, calculados desde la base de
    datos.

    Lee la sesion sin modificarla: `read_cart` limpia un carrito de version
    anterior y eso borraria el aviso de reinicio que muestra la vista del
    carrito."""
    sesion = request.session
    carrito = {}
    if sesion.get(SESSION_VERSION_KEY) == CART_VERSION:
        carrito = sesion.get(SESSION_CART_KEY) or {}
    contexto = build_cart_context(carrito)
    lineas = [
        {
            'variant_id': item['variant'].id,
            'qty': item['cantidad'],
            'sku': item['variant'].sku,
            'unit_price': evidencia.precio_texto(item['precio']),
            'available': get_available_quantity(item['variant']),
        }
        for item in contexto['items'][: contrato.MAX_LINEAS_CARRITO]
    ]
    ids_de_producto = list(dict.fromkeys(item['producto'].id for item in contexto['items']))
    carrito_armado = {
        'count': contexto['num_items'],
        'subtotal': evidencia.precio_texto(contexto['subtotal']),
        'lines': lineas,
    }
    return carrito_armado, ids_de_producto


def linea_de_ropa_preferida(request):
    """'dama', 'caballero' o '' segun lo que la persona eligio en Mi cuenta.

    Es una preferencia de compra que ella misma guardo para que le recomienden
    esa linea, no un dato de su identidad; viaja sola, sin nada que la
    identifique."""
    user = request.user
    if not user.is_authenticated:
        return ''
    preferencia = getattr(user, 'clothing_line', '') or ''
    return preferencia if preferencia in contrato.LINEAS_PREFERIDAS else ''


def pagos_en_vivo():
    """True solo si el cobro es real: proveedor no simulado, con credenciales
    y con los pagos en linea habilitados en el panel. El agente no debe
    prometer medios de pago que la tienda aun no puede recibir."""
    return (
        settings.PAYMENT_PROVIDER == 'mercadopago'
        and bool(settings.MERCADOPAGO_ACCESS_TOKEN)
        and pagos_habilitados()
    )


def contexto_del_cliente(user):
    """Datos que solo Prime tiene y que el cliente autorizo: orientacion de
    talla (sin centimetros) y elecciones que confirmo con "Recordar". Vacio
    si no hay permisos vigentes. El Coach vuelve a exigir los scopes de la
    asercion antes de usarlos."""
    consent = CommercePersonalizationConsent.objects.filter(user=user).first()
    if consent is None:
        return {}
    contexto = {}
    if consent.is_active('tailoring.measurements'):
        guia = talla.orientacion(user)
        if guia:
            contexto['size_hint'] = guia
    if consent.is_active('conversation.commerce_memory'):
        recuerdos = [
            {'kind': item.kind, 'value': item.value}
            for item in CommerceMemoryItem.objects.filter(user=user, expires_at__gt=timezone.now()).order_by('kind')
        ]
        if recuerdos:
            contexto['memory'] = recuerdos
    return contexto


def bloque_visual(descripcion, coincidencias):
    """`visual_query`: lo que el Coach vio en la foto del visitante y los
    productos de la tienda que se le parecen, con los atributos en que
    coinciden. La foto no viaja en el turno."""
    return {
        'source': 'customer_photo',
        'vocabulary_version': atributos.VERSION_VOCABULARIO,
        'garment_detected': descripcion.prenda,
        'person_present': descripcion.persona,
        'attributes': dict(descripcion.atributos),
        'matches': [dict(fila) for fila in coincidencias],
    }


def bloque_adjunto(leido):
    """`attachment`: el extracto de un archivo que adjunto el visitante
    (documento.leer), ya sin datos personales evidentes ni nombre de archivo."""
    return {
        'source': 'customer_document',
        'format': leido.formato,
        'excerpt': leido.extracto,
        'truncated': leido.recortado,
    }


def armar_solicitud(request, mensaje, conversation_id, request_id=None, ahora=None, visual=None, adjunto=None):
    """Solicitud lista para firmar y enviar.

    `visual` es el bloque de `bloque_visual` cuando el turno viene de una
    foto: sus coincidencias van primero entre los candidatos.

    `adjunto` es el bloque de `bloque_adjunto` cuando el turno trae un
    archivo: su texto tambien sirve para elegir candidatos (una lista de
    prendas, por ejemplo).

    Lanza `ContratoInvalido` si el paquete no respeta el contrato o no cabe
    en el presupuesto incluso despues de descartar candidatos: en ese caso no
    se envia nada."""
    idioma = idioma_del_visitante()
    sujeto, autenticado = sujeto_del_visitante(request)
    pagina = contexto_de_pagina(request)
    carrito, productos_del_carrito = carrito_de_la_sesion(request)
    linea_preferida = linea_de_ropa_preferida(request)
    visitante = {'subject': sujeto, 'authenticated': autenticado}
    if linea_preferida:
        visitante['line_preference'] = linea_preferida

    solicitud = {
        'request_id': request_id or str(uuid.uuid4()),
        'conversation_id': conversation_id,
        'locale': idioma,
        'message': mensaje.strip(),
        'visitor': visitante,
        'page': pagina,
        'cart': carrito,
        'shop_flags': {
            'purchases_paused': bool(compras_pausadas()),
            'payments_live': pagos_en_vivo(),
            'currency': contrato.MONEDA,
        },
        'evidence': {
            'candidates': evidencia.candidatos(
                f"{mensaje}\n{adjunto['excerpt']}" if adjunto else mensaje,
                foco_id=pagina['product_id'], ids_carrito=productos_del_carrito,
                linea_preferida=linea_preferida,
                primero=[fila['product_id'] for fila in (visual or {}).get('matches', [])],
            ),
            'policies': evidencia.politicas(idioma),
            'promotions': evidencia.promociones(),
            'claims_policy': evidencia.afirmaciones_prohibidas(),
        },
        'timestamp': int(time.time() if ahora is None else ahora),
    }

    # Si no cabe, se pierden primero los candidatos del final (los que menos
    # tienen que ver con el visitante), nunca el producto en foco ni el carrito.
    if settings.VENDEDOR_CONTRATO_V2 and autenticado:
        bloque = identidad.emitir(request.user, ahora=ahora)
        if bloque is not None:
            solicitud['identity'] = bloque
            contexto = contexto_del_cliente(request.user)
            if contexto:
                solicitud['customer_context'] = contexto

    if visual is not None:
        solicitud['visual_query'] = visual
    if adjunto is not None:
        solicitud['attachment'] = adjunto

    candidatos = solicitud['evidence']['candidates']
    while candidatos and contrato.tamano_en_bytes(solicitud) > contrato.MAX_BYTES_SOLICITUD:
        candidatos.pop()
        if visual is not None:
            # Una coincidencia sin su candidato no le sirve al Coach.
            presentes = {c['product_id'] for c in candidatos}
            visual['matches'] = [f for f in visual['matches'] if f['product_id'] in presentes]

    contrato.validar_solicitud(solicitud)
    return solicitud

