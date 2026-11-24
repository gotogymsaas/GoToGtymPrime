"""Interruptores del panel que la tienda consulta (pausa de compras, recibir
pagos).

Viven en una utilidad compartida, y no en `administracion`, porque carrito,
pedidos y pagos los leen en cada peticion y no pueden depender del panel. El
modelo se resuelve por nombre para no importar ninguna app."""
from datetime import timedelta

from django.apps import apps
from django.utils import timezone
from django.utils.translation import gettext_lazy

# Cuanto dura encendido el modo "Confirmar sin pagar (equipo)". Se comprueba
# al leerlo, sin depender de ninguna tarea periodica: pasado el plazo el modo
# deja de aplicar aunque el interruptor siga marcado en la base de datos.
VIGENCIA_MODO_SIN_PAGO = timedelta(hours=24)

MENSAJE_COMPRAS_PAUSADAS = gettext_lazy(
    'Las compras están en pausa temporalmente. Vuelve pronto: tu carrito se conserva.'
)

MENSAJE_PAGOS_DESHABILITADOS = gettext_lazy(
    'Los pagos en línea están deshabilitados temporalmente. Tu pedido queda guardado: vuelve más tarde para pagarlo.'
)


# Valor de cada interruptor mientras la fila de configuracion no existe.
_POR_DEFECTO = {
    'purchases_paused': False,
    'online_payments_enabled': True,
    'coach_enabled': True,
    'staff_checkout_without_payment': False,
}


_ENCENDIDO_EN = 'staff_checkout_without_payment_since'
_VENCE_EL = 'staff_checkout_without_payment_vence'


def _leer_todos():
    """Todos los interruptores en una sola consulta (sin crear la fila).

    El modo "Confirmar sin pagar" solo vale si esta marcado, tiene fecha de
    encendido y no han pasado `VIGENCIA_MODO_SIN_PAGO`: una marca sin fecha
    (puesta por fuera del panel) se trata como vencida. Ademas del valor,
    devuelve cuando vence (`None` si no esta activo)."""
    modelo = apps.get_model('administracion', 'PanelSettings')
    fila = modelo.objects.filter(pk=1).values(*_POR_DEFECTO, _ENCENDIDO_EN).first() or {}
    ajustes = {
        campo: por_defecto if fila.get(campo) is None else bool(fila[campo])
        for campo, por_defecto in _POR_DEFECTO.items()
    }
    encendido_en = fila.get(_ENCENDIDO_EN)
    vence = encendido_en + VIGENCIA_MODO_SIN_PAGO if encendido_en else None
    activo = ajustes['staff_checkout_without_payment'] and vence is not None and timezone.now() < vence
    ajustes['staff_checkout_without_payment'] = activo
    ajustes[_VENCE_EL] = vence if activo else None
    return ajustes


def _ajuste(campo, request=None):
    """Valor de un interruptor. Con `request`, la primera lectura de la
    peticion se recuerda en ella: una pagina consulta varios interruptores
    (plantillas, procesadores de contexto, visibilidad del asistente) y todos
    comparten una sola consulta. Se guarda en la peticion y no en la cache
    compartida para que un cambio del panel se vea en la siguiente peticion,
    sin esperar ningun vencimiento."""
    if request is None:
        return _leer_todos()[campo]
    ajustes = getattr(request, '_ajustes_tienda', None)
    if ajustes is None:
        ajustes = request._ajustes_tienda = _leer_todos()
    return ajustes[campo]


def compras_pausadas(request=None):
    return _ajuste('purchases_paused', request)


def pagos_habilitados(request=None):
    return _ajuste('online_payments_enabled', request)


def modo_sin_pago_activo(request=None):
    """Interruptor "Confirmar sin pagar (equipo)" del panel."""
    return _ajuste('staff_checkout_without_payment', request)


def modo_sin_pago_vence_el(request=None):
    """Momento en que el modo de pruebas deja de aplicar, o `None` si no esta
    activo."""
    return _ajuste(_VENCE_EL, request)


def confirma_sin_pagar(request):
    """Si quien hace esta peticion confirma sus pedidos sin pagar: solo una
    cuenta del equipo, y solo con el modo de pruebas encendido. Un cliente
    paga siempre, este o no encendido."""
    usuario = getattr(request, 'user', None)
    return bool(usuario is not None and usuario.is_authenticated and usuario.is_staff
                and modo_sin_pago_activo(request))


def coach_habilitado(request=None):
    """Decision del administrador de mostrar o no el asistente de compras con
    IA. Sin fila todavia vale el valor por defecto: habilitado."""
    return _ajuste('coach_enabled', request)
