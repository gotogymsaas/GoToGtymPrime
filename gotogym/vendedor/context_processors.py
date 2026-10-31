from .exposicion import visible_para


def vendedor(request):
    """Expone a las plantillas si se muestra el boton del vendedor. Con el
    interruptor apagado o fuera del grupo expuesto, el sitio es identico al de
    antes: ni boton ni panel."""
    return {'vendedor_visible': visible_para(request)}
