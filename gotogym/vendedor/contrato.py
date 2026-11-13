"""Contrato entre la tienda y el servicio de IA (Coach).

Es la unica descripcion de lo que viaja en cada sentido. La tienda arma la
solicitud y valida la respuesta con las funciones de este modulo; los
ejemplos de `ejemplos/` pasan por las mismas funciones en las pruebas, de modo
que el equipo del Coach puede usarlos como prueba de aceptacion.

Este modulo no consulta la base de datos. Comprueba la forma y los limites
(tipos, longitudes, lista blanca de acciones); que un producto exista, este
activo y tenga stock se comprueba despues, en `respuesta.py`, contra la base.

Los mensajes de error nombran el campo, nunca su contenido: el texto del
visitante o del modelo no debe acabar en logs ni en Sentry.
"""
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

VERSION_CONTRATO = '1'
# v2 = v1 + bloque opcional `identity`. Solo se envia si el Coach lo soporta
# (VENDEDOR_CONTRATO_V2) y hay asercion; si no, el paquete sale como v1.
VERSION_CONTRATO_V2 = '2'
CLAVES_IDENTIDAD = frozenset({'key_id', 'assertion', 'signature'})
MAX_LARGO_ASERCION = 1024
# Cupones de libre acceso (evidencia.promociones). Nunca los de afiliados.
MAX_PROMOCIONES = 5
CLAVES_PROMOCION = frozenset({'code', 'discount_type', 'value', 'min_purchase', 'ends_on'})

# Presupuesto de la solicitud. El proveedor del modelo ya rechazo con HTTP 429
# solicitudes muy grandes, asi que el tope es duro: el paquete se recorta antes
# de firmarlo y, si aun asi no cabe, no se envia.
MAX_BYTES_SOLICITUD = 24 * 1024
MAX_CANDIDATOS = 8
MAX_VARIANTES_POR_CANDIDATO = 24
MAX_LINEAS_CARRITO = 20
MAX_POLITICAS = 8
MAX_LARGO_MENSAJE = 600
MAX_LARGO_DESCRIPCION = 300
# Una politica no se recorta: cortarla a media frase cambia lo que dice. Si
# crece por encima de este tope, el armado del paquete falla y una prueba lo
# hace visible antes de llegar a produccion.
MAX_LARGO_POLITICA = 1800

# Limites de la respuesta. Un texto que no cabe se rechaza entero: recortar la
# respuesta de un modelo deja frases a medias.
MAX_LARGO_RESPUESTA = 2000
MAX_LARGO_RAZON = 280
MAX_LARGO_ETIQUETA = 60
MAX_ACCIONES = 4
MAX_TARJETAS = 8
MAX_SEGUNDOS_REINTENTO = 3600

IDIOMAS = ('es', 'en')
MONEDA = 'COP'

ACCIONES_PERMITIDAS = frozenset({'add_to_cart', 'open_product', 'go_checkout', 'open_contact', 'open_solution'})
# Claves de `open_solution`. La direccion de cada una la pone la tienda.
SOLUCIONES_PERMITIDAS = frozenset({'coach_app', 'developers'})
# Linea de cada candidato y preferencia de la persona (products/linea.py).
LINEAS_DE_PRODUCTO = frozenset({'dama', 'caballero', 'unisex'})
LINEAS_PREFERIDAS = frozenset({'dama', 'caballero'})
ESTADOS_RESPUESTA = frozenset({'ok', 'error'})
ESTADOS_REVISION = frozenset({'validated', 'pending_review'})

# Nombres de campo que nunca deben aparecer en una solicitud. Es una red de
# seguridad sobre el armado del paquete, no el unico control: el paquete se
# construye con una lista cerrada de campos.
CAMPOS_PROHIBIDOS = frozenset({
    'email', 'correo', 'phone', 'telefono', 'document', 'documento',
    'address', 'direccion', 'password', 'contrasena', 'token', 'referral_code',
    'affiliate_code', 'codigo_afiliado', 'first_name', 'last_name', 'nombre_cliente',
})

_PRECIO = re.compile(r'^\d{1,12}(\.\d{1,4})?$')
_PREFIJOS_SUJETO = ('shop_v_', 'shop_u_')


class ContratoInvalido(ValueError):
    """La solicitud o la respuesta no respeta el contrato. El mensaje nombra el
    campo y no incluye su valor."""


@dataclass(frozen=True)
class AccionPropuesta:
    tipo: str
    variant_id: int | None = None
    product_id: int | None = None
    etiqueta: str = ''
    solucion: str = ''


@dataclass(frozen=True)
class TarjetaPropuesta:
    product_id: int
    razon: str


@dataclass(frozen=True)
class MetaRespuesta:
    agentes: tuple[str, ...] = ()
    referencias: tuple[str, ...] = ()
    estado: str = 'ok'
    reintentar_en: int | None = None
    # Motivo corto que da el Coach cuando no responde (p. ej. `validation_failed`).
    # Solo sirve para el registro: nunca se muestra al visitante.
    codigo_error: str = ''


_CODIGO_ERROR = re.compile(r'^[a-z0-9_]{1,40}$')


@dataclass(frozen=True)
class RespuestaCoach:
    texto: str
    acciones: tuple[AccionPropuesta, ...] = ()
    tarjetas: tuple[TarjetaPropuesta, ...] = ()
    handoff: dict | None = None
    meta: MetaRespuesta = field(default_factory=MetaRespuesta)
    # Acciones o tarjetas que el contrato descarto (fuera de lista blanca,
    # mal formadas o por encima del tope). Sirve para medir, no se muestra.
    descartadas: int = 0

    @property
    def ok(self):
        return self.meta.estado == 'ok'


def serializar(solicitud):
    """Bytes exactos que se firman y se envian."""
    return json.dumps(
        solicitud, ensure_ascii=False, separators=(',', ':'), sort_keys=True,
    ).encode('utf-8')


def tamano_en_bytes(solicitud):
    return len(serializar(solicitud))


def _entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def _requerir(condicion, campo):
    if not condicion:
        raise ContratoInvalido(campo)


def _texto(valor, campo, maximo, vacio=False):
    _requerir(isinstance(valor, str), campo)
    _requerir(vacio or valor.strip() != '', campo)
    _requerir(len(valor) <= maximo, campo)
    return valor


def _decimal_texto(valor, campo):
    """Los precios viajan como texto decimal: un float pierde exactitud y un
    entero esconde que son pesos con centavos."""
    _requerir(isinstance(valor, str) and _PRECIO.match(valor) is not None, campo)
    try:
        Decimal(valor)
    except InvalidOperation:
        raise ContratoInvalido(campo) from None
    return valor


def _buscar_campos_prohibidos(valor, ruta='solicitud'):
    if isinstance(valor, dict):
        for clave, contenido in valor.items():
            _requerir(str(clave).lower() not in CAMPOS_PROHIBIDOS, f'{ruta}.{clave}')
            _buscar_campos_prohibidos(contenido, f'{ruta}.{clave}')
    elif isinstance(valor, list):
        for posicion, contenido in enumerate(valor):
            _buscar_campos_prohibidos(contenido, f'{ruta}[{posicion}]')


def _validar_variante(variante, ruta):
    _requerir(isinstance(variante, dict), ruta)
    _requerir(_entero(variante.get('id')), f'{ruta}.id')
    _texto(variante.get('size'), f'{ruta}.size', 20, vacio=True)
    _texto(variante.get('color'), f'{ruta}.color', 40, vacio=True)
    _decimal_texto(variante.get('price'), f'{ruta}.price')
    _requerir(_entero(variante.get('available')) and variante['available'] >= 0, f'{ruta}.available')
    if 'list_price' in variante:
        _decimal_texto(variante['list_price'], f'{ruta}.list_price')


def _validar_candidato(candidato, ruta):
    _requerir(isinstance(candidato, dict), ruta)
    _requerir(_entero(candidato.get('product_id')), f'{ruta}.product_id')
    _texto(candidato.get('name'), f'{ruta}.name', 150)
    _decimal_texto(candidato.get('price'), f'{ruta}.price')
    _texto(candidato.get('description'), f'{ruta}.description', MAX_LARGO_DESCRIPCION, vacio=True)
    _texto(candidato.get('url'), f'{ruta}.url', 300)
    _requerir(candidato['url'].startswith('/'), f'{ruta}.url')
    _requerir(candidato.get('line', 'dama') in LINEAS_DE_PRODUCTO, f'{ruta}.line')
    variantes = candidato.get('variants')
    _requerir(isinstance(variantes, list) and 0 < len(variantes) <= MAX_VARIANTES_POR_CANDIDATO,
              f'{ruta}.variants')
    for posicion, variante in enumerate(variantes):
        _validar_variante(variante, f'{ruta}.variants[{posicion}]')


def _validar_linea(linea, ruta):
    _requerir(isinstance(linea, dict), ruta)
    _requerir(_entero(linea.get('variant_id')), f'{ruta}.variant_id')
    _requerir(_entero(linea.get('qty')) and linea['qty'] > 0, f'{ruta}.qty')
    _texto(linea.get('sku'), f'{ruta}.sku', 60)
    _decimal_texto(linea.get('unit_price'), f'{ruta}.unit_price')
    _requerir(_entero(linea.get('available')) and linea['available'] >= 0, f'{ruta}.available')


def _validar_politica(politica, ruta):
    _requerir(isinstance(politica, dict), ruta)
    _texto(politica.get('key'), f'{ruta}.key', 40)
    _texto(politica.get('title'), f'{ruta}.title', 120)
    _texto(politica.get('text'), f'{ruta}.text', MAX_LARGO_POLITICA)
    _texto(politica.get('version'), f'{ruta}.version', 40)
    _requerir(politica.get('review_status') in ESTADOS_REVISION, f'{ruta}.review_status')


_TALLAS_GUIA = frozenset({'XS', 'S', 'M', 'L', 'XL', 'XXL', 'out_of_guide'})
_COLUMNAS_GUIA = frozenset({'busto', 'cintura', 'cadera'})
_TIPOS_MEMORIA = frozenset({'size', 'fit', 'color', 'activity'})


def _validar_contexto_cliente(contexto):
    """Forma cerrada del bloque v2 `customer_context` (ver paquete.contexto_del_cliente)."""
    _requerir(isinstance(contexto, dict) and contexto and set(contexto) <= {'size_hint', 'memory'}, 'customer_context')
    guia = contexto.get('size_hint')
    if guia is not None:
        _requerir(isinstance(guia, dict) and set(guia) == {'source', 'by_dimension', 'suggestion', 'measured_on'},
                  'customer_context.size_hint')
        _requerir(guia['source'] == 'general_size_guide', 'customer_context.size_hint')
        por = guia['by_dimension']
        _requerir(isinstance(por, dict) and por and set(por) <= _COLUMNAS_GUIA
                  and all(v in _TALLAS_GUIA for v in por.values()), 'customer_context.size_hint')
        _requerir(guia['suggestion'] is None or guia['suggestion'] in _TALLAS_GUIA - {'out_of_guide'},
                  'customer_context.size_hint')
        _requerir(re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(guia['measured_on'])) is not None, 'customer_context.size_hint')
    recuerdos = contexto.get('memory')
    if recuerdos is not None:
        _requerir(isinstance(recuerdos, list) and 0 < len(recuerdos) <= 8, 'customer_context.memory')
        for item in recuerdos:
            _requerir(isinstance(item, dict) and set(item) == {'kind', 'value'} and item['kind'] in _TIPOS_MEMORIA,
                      'customer_context.memory')
            _texto(item['value'], 'customer_context.memory', 40)


def validar_solicitud(solicitud):
    """Comprueba que `solicitud` (un dict) cumple el contrato. No devuelve
    nada: lanza `ContratoInvalido` ante el primer incumplimiento."""
    _requerir(isinstance(solicitud, dict), 'solicitud')
    _buscar_campos_prohibidos(solicitud)

    _texto(solicitud.get('request_id'), 'request_id', 64)
    _texto(solicitud.get('conversation_id'), 'conversation_id', 64)
    _requerir(solicitud['conversation_id'].startswith('shop-'), 'conversation_id')
    _requerir(solicitud.get('locale') in IDIOMAS, 'locale')
    _texto(solicitud.get('message'), 'message', MAX_LARGO_MENSAJE)
    _requerir(_entero(solicitud.get('timestamp')) and solicitud['timestamp'] > 0, 'timestamp')

    visitante = solicitud.get('visitor')
    _requerir(isinstance(visitante, dict), 'visitor')
    _texto(visitante.get('subject'), 'visitor.subject', 80)
    _requerir(visitante['subject'].startswith(_PREFIJOS_SUJETO), 'visitor.subject')
    _requerir(isinstance(visitante.get('authenticated'), bool), 'visitor.authenticated')
    if 'line_preference' in visitante:
        _requerir(visitante['authenticated'] and visitante['line_preference'] in LINEAS_PREFERIDAS,
                  'visitor.line_preference')

    # v2: asercion de identidad opcional (vendedor/identidad.py). Solo su
    # forma; la firma y la vigencia las comprueba el Coach.
    if 'identity' in solicitud:
        identidad = solicitud['identity']
        _requerir(isinstance(identidad, dict) and set(identidad) == CLAVES_IDENTIDAD, 'identity')
        _texto(identidad.get('key_id'), 'identity.key_id', 40)
        _texto(identidad.get('assertion'), 'identity.assertion', MAX_LARGO_ASERCION)
        _requerir(re.fullmatch(r'[0-9a-f]{64}', str(identidad.get('signature'))) is not None,
                  'identity.signature')
        _requerir(visitante['authenticated'] and visitante['subject'].startswith('shop_u_'), 'identity')

    if 'customer_context' in solicitud:
        _requerir('identity' in solicitud, 'customer_context')
        _validar_contexto_cliente(solicitud['customer_context'])

    pagina = solicitud.get('page')
    _requerir(isinstance(pagina, dict), 'page')
    _texto(pagina.get('url_name'), 'page.url_name', 80, vacio=True)
    for campo in ('product_id', 'variant_id'):
        _requerir(pagina.get(campo) is None or _entero(pagina[campo]), f'page.{campo}')
    _texto(pagina.get('filtro', ''), 'page.filtro', 100, vacio=True)

    carrito = solicitud.get('cart')
    _requerir(isinstance(carrito, dict), 'cart')
    _requerir(_entero(carrito.get('count')) and carrito['count'] >= 0, 'cart.count')
    _decimal_texto(carrito.get('subtotal'), 'cart.subtotal')
    lineas = carrito.get('lines')
    _requerir(isinstance(lineas, list) and len(lineas) <= MAX_LINEAS_CARRITO, 'cart.lines')
    for posicion, linea in enumerate(lineas):
        _validar_linea(linea, f'cart.lines[{posicion}]')

    banderas = solicitud.get('shop_flags')
    _requerir(isinstance(banderas, dict), 'shop_flags')
    _requerir(isinstance(banderas.get('purchases_paused'), bool), 'shop_flags.purchases_paused')
    _requerir(isinstance(banderas.get('payments_live'), bool), 'shop_flags.payments_live')
    _requerir(banderas.get('currency') == MONEDA, 'shop_flags.currency')

    evidencia = solicitud.get('evidence')
    _requerir(isinstance(evidencia, dict), 'evidence')
    candidatos = evidencia.get('candidates')
    _requerir(isinstance(candidatos, list) and len(candidatos) <= MAX_CANDIDATOS, 'evidence.candidates')
    for posicion, candidato in enumerate(candidatos):
        _validar_candidato(candidato, f'evidence.candidates[{posicion}]')
    politicas = evidencia.get('policies', [])
    _requerir(isinstance(politicas, list) and len(politicas) <= MAX_POLITICAS, 'evidence.policies')
    for posicion, politica in enumerate(politicas):
        _validar_politica(politica, f'evidence.policies[{posicion}]')
    promociones = evidencia.get('promotions', [])
    _requerir(isinstance(promociones, list) and len(promociones) <= MAX_PROMOCIONES, 'evidence.promotions')
    for posicion, promo in enumerate(promociones):
        ruta = f'evidence.promotions[{posicion}]'
        _requerir(isinstance(promo, dict) and set(promo) == CLAVES_PROMOCION, ruta)
        _requerir(re.fullmatch(r'[A-Z0-9_-]{1,30}', str(promo['code'])) is not None, f'{ruta}.code')
        _requerir(promo['discount_type'] in ('percentage', 'fixed'), f'{ruta}.discount_type')
        _decimal_texto(promo['value'], f'{ruta}.value')
        if promo['min_purchase'] is not None:
            _decimal_texto(promo['min_purchase'], f'{ruta}.min_purchase')
        _requerir(promo['ends_on'] is None or re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(promo['ends_on'])),
                  f'{ruta}.ends_on')
    afirmaciones = evidencia.get('claims_policy')
    _requerir(isinstance(afirmaciones, dict), 'evidence.claims_policy')
    _texto(afirmaciones.get('version'), 'evidence.claims_policy.version', 64)
    prohibidas = afirmaciones.get('prohibited')
    _requerir(isinstance(prohibidas, list) and all(isinstance(t, str) for t in prohibidas),
              'evidence.claims_policy.prohibited')

    _requerir(tamano_en_bytes(solicitud) <= MAX_BYTES_SOLICITUD, 'solicitud.tamano')


def _entero_opcional(valor, campo):
    _requerir(valor is None or (_entero(valor) and valor >= 0), campo)
    return valor


def _lista_de_textos(valor, campo, maximo_items=20, maximo_largo=120):
    if valor is None:
        return ()
    _requerir(isinstance(valor, list) and len(valor) <= maximo_items, campo)
    for item in valor:
        _texto(item, campo, maximo_largo)
    return tuple(valor)


def _leer_accion(cruda):
    """`AccionPropuesta` si la accion es valida y permitida, `None` si se debe
    descartar. Una accion malformada se descarta, no invalida la respuesta."""
    if not isinstance(cruda, dict) or cruda.get('type') not in ACCIONES_PERMITIDAS:
        return None
    tipo = cruda['type']
    variant_id = cruda.get('variant_id')
    product_id = cruda.get('product_id')
    if tipo == 'add_to_cart' and not _entero(variant_id):
        return None
    if tipo == 'open_product' and not _entero(product_id):
        return None
    solucion = cruda.get('solution', '') if tipo == 'open_solution' else ''
    if tipo == 'open_solution' and solucion not in SOLUCIONES_PERMITIDAS:
        return None
    etiqueta = cruda.get('label', '')
    if not isinstance(etiqueta, str) or len(etiqueta) > MAX_LARGO_ETIQUETA:
        etiqueta = ''
    return AccionPropuesta(
        tipo=tipo,
        variant_id=variant_id if _entero(variant_id) else None,
        product_id=product_id if _entero(product_id) else None,
        etiqueta=etiqueta,
        solucion=solucion,
    )


def validar_respuesta(datos):
    """Convierte la respuesta del Coach en un `RespuestaCoach`.

    Lanza `ContratoInvalido` si la estructura no es utilizable (no es un
    objeto, falta `meta`, el texto no cabe). Las acciones y tarjetas
    individuales mal formadas o no permitidas se descartan y se cuentan en
    `descartadas`. Los campos desconocidos se ignoran para que el Coach pueda
    agregar informacion sin romper a la tienda.
    """
    _requerir(isinstance(datos, dict), 'respuesta')
    crudo_meta = datos.get('meta')
    _requerir(isinstance(crudo_meta, dict), 'meta')
    estado = crudo_meta.get('status')
    _requerir(estado in ESTADOS_RESPUESTA, 'meta.status')
    # Un codigo con otra forma se ignora en vez de rechazar la respuesta: el
    # motivo es informativo y llega a los logs, asi que no se acepta texto libre.
    codigo_error = crudo_meta.get('error_code')
    if not (isinstance(codigo_error, str) and _CODIGO_ERROR.match(codigo_error)):
        codigo_error = ''
    meta = MetaRespuesta(
        agentes=_lista_de_textos(crudo_meta.get('agents_used'), 'meta.agents_used', 12, 40),
        referencias=_lista_de_textos(crudo_meta.get('evidence_refs'), 'meta.evidence_refs', 40, 120),
        estado=estado,
        reintentar_en=_entero_opcional(crudo_meta.get('retry_after_seconds'), 'meta.retry_after_seconds'),
        codigo_error=codigo_error,
    )
    _requerir(meta.reintentar_en is None or meta.reintentar_en <= MAX_SEGUNDOS_REINTENTO,
              'meta.retry_after_seconds')

    if estado != 'ok':
        # En un error el texto no se usa: la tienda muestra su propio mensaje.
        return RespuestaCoach(texto='', meta=meta)

    texto = _texto(datos.get('reply'), 'reply', MAX_LARGO_RESPUESTA)

    descartadas = 0
    acciones = []
    crudas = datos.get('ui_actions') or []
    _requerir(isinstance(crudas, list), 'ui_actions')
    for cruda in crudas:
        accion = _leer_accion(cruda)
        if accion is None or len(acciones) >= MAX_ACCIONES:
            descartadas += 1
        else:
            acciones.append(accion)

    tarjetas = []
    crudas = datos.get('product_cards') or []
    _requerir(isinstance(crudas, list), 'product_cards')
    for cruda in crudas:
        valida = (
            isinstance(cruda, dict)
            and _entero(cruda.get('product_id'))
            and isinstance(cruda.get('reason', ''), str)
            and len(cruda.get('reason', '')) <= MAX_LARGO_RAZON
        )
        if not valida or len(tarjetas) >= MAX_TARJETAS:
            descartadas += 1
        else:
            tarjetas.append(TarjetaPropuesta(product_id=cruda['product_id'], razon=cruda.get('reason', '')))

    handoff = datos.get('handoff')
    _requerir(handoff is None or isinstance(handoff, dict), 'handoff')
    if handoff is not None:
        categoria = handoff.get('category', '')
        motivo = handoff.get('reason', '')
        _requerir(isinstance(categoria, str) and len(categoria) <= 40, 'handoff.category')
        _requerir(isinstance(motivo, str) and len(motivo) <= 200, 'handoff.reason')
        handoff = {'category': categoria, 'reason': motivo}

    return RespuestaCoach(
        texto=texto,
        acciones=tuple(acciones),
        tarjetas=tuple(tarjetas),
        handoff=handoff,
        meta=meta,
        descartadas=descartadas,
    )
