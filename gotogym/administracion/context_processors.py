from .models import PanelSettings


def compras_pausadas(request):
    """Expone a las plantillas (tienda y panel) si las compras estan en
    pausa: la tienda muestra el aviso y el panel pinta el interruptor."""
    return {'compras_pausadas': PanelSettings.compras_pausadas()}


def pagos_habilitados(request):
    """Expone a las plantillas si se reciben pagos en linea: la tienda oculta
    el boton de pago y el panel pinta el interruptor "Recibir pagos"."""
    return {'pagos_habilitados': PanelSettings.pagos_habilitados()}
