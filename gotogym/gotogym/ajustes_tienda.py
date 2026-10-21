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


def _ajuste(campo, por_defecto):
    """Lectura liviana (sin crear la fila): sin fila todavia vale el valor por
    defecto del campo."""
    modelo = apps.get_model('administracion', 'PanelSettings')
    valor = modelo.objects.filter(pk=1).values_list(campo, flat=True).first()
    return por_defecto if valor is None else bool(valor)


def compras_pausadas():
    return _ajuste('purchases_paused', False)


def pagos_habilitados():
    return _ajuste('online_payments_enabled', True)
