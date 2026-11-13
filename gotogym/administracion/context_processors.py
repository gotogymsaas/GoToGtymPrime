from gotogym import ajustes_tienda


def compras_pausadas(request):
    """Expone a las plantillas (tienda y panel) si las compras estan en
    pausa: la tienda muestra el aviso y el panel pinta el interruptor."""
    return {'compras_pausadas': ajustes_tienda.compras_pausadas(request)}


def pagos_habilitados(request):
    """Expone a las plantillas si se reciben pagos en linea: la tienda oculta
    el boton de pago y el panel pinta el interruptor "Recibir pagos"."""
    return {'pagos_habilitados': ajustes_tienda.pagos_habilitados(request)}


def coach_habilitado(request):
    """Expone al panel si el asistente (Coach) esta habilitado: pinta el
    interruptor "Habilitar Coach" de la barra superior."""
    return {'coach_habilitado': ajustes_tienda.coach_habilitado(request)}
