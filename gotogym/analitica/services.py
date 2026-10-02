"""Identidad de visitante y eventos emitidos por el servidor.

Dos decisiones de medicion viven aqui porque las usan tanto la vista que
recibe los eventos del navegador como el codigo del checkout.

**Visitante estable, no clave de sesion.** Django rota la clave de sesion al
iniciar sesion (`cycle_key`), pero conserva los datos. Si se agrupara por el
hash de la clave, quien agrega al carrito como anonimo y se identifica en el
checkout pasaria a ser "otra persona" justo en el paso que mas interesa
medir, y el embudo se partiria en dos. Por eso se guarda un identificador
aleatorio dentro de la propia sesion, que sobrevive a la rotacion, y se
agrupa por su hash. No identifica a nadie: es un numero al azar, sin
relacion con el usuario, y se pierde cuando caduca la sesion.

**Eventos de servidor.** Algunos hechos (un pedido creado) son mas fiables
medidos donde ocurren que desde el navegador, donde un bloqueador de
anuncios los eliminaria. Esos eventos no se aceptan desde el cliente (ver
`EVENTOS_SERVIDOR`): si se aceptaran, cualquiera podria fabricar pedidos en
el embudo.
"""
import hashlib
import logging
import uuid

from django.conf import settings

from .models import EventoAnalitica

logger = logging.getLogger(__name__)

CLAVE_VISITANTE = 'analitica_vid'

# Nunca llegan por el endpoint publico; solo los emite el servidor.
EVENTOS_SERVIDOR = frozenset({
    'order_created',
})


def hash_visitante(request):
    """Hash estable por visitante (sobrevive al login), no reversible."""
    visitante = request.session.get(CLAVE_VISITANTE)
    if not visitante:
        visitante = uuid.uuid4().hex
        request.session[CLAVE_VISITANTE] = visitante
    semilla = f'{settings.SECRET_KEY}:{visitante}'.encode()
    return hashlib.sha256(semilla).hexdigest()[:32]


def no_medir(request):
    """True si el visitante pidio no ser medido (Do Not Track o GPC).

    El script del navegador ya lo respeta; el servidor lo comprueba tambien
    para sus propios eventos.
    """
    return request.headers.get('DNT') == '1' or request.headers.get('Sec-GPC') == '1'


def registrar_evento(request, nombre, **propiedades):
    """Guarda un evento emitido por el servidor.

    Medir nunca debe romper la compra: cualquier fallo se registra en el log
    y se descarta.
    """
    if nombre not in EVENTOS_SERVIDOR or no_medir(request):
        return None
    try:
        return EventoAnalitica.objects.create(
            nombre=nombre,
            ruta=request.path[:300],
            sesion=hash_visitante(request),
            autenticado=request.user.is_authenticated,
            propiedades=propiedades,
        )
    except Exception:
        logger.exception('No se pudo registrar el evento de servidor %s', nombre)
        return None
