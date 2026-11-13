"""Interruptores del panel que la tienda consulta (pausa de compras, recibir
pagos).

Viven en una utilidad compartida, y no en `administracion`, porque carrito,
pedidos y pagos los leen en cada peticion y no pueden depender del panel. El
modelo se resuelve por nombre para no importar ninguna app."""
from django.apps import apps
from django.utils.translation import gettext_lazy

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
}


def _leer_todos():
    """Los tres interruptores en una sola consulta (sin crear la fila)."""
    modelo = apps.get_model('administracion', 'PanelSettings')
    fila = modelo.objects.filter(pk=1).values(*_POR_DEFECTO).first() or {}
    return {
        campo: por_defecto if fila.get(campo) is None else bool(fila[campo])
        for campo, por_defecto in _POR_DEFECTO.items()
    }


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


def coach_habilitado(request=None):
    """Decision del administrador de mostrar o no el asistente de compras con
    IA. Sin fila todavia vale el valor por defecto: habilitado."""
    return _ajuste('coach_enabled', request)
