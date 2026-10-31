from .exposicion import coach_configurado, visible_para


def vendedor(request):
    """Expone a las plantillas si se muestra el boton de Quantum Coach y si
    hay una IA que responda. Con el interruptor apagado o fuera del grupo
    expuesto, el sitio es identico al de antes: ni boton ni panel. Sin IA
    configurada se muestra igual y el panel avisa que no esta disponible."""
    visible = visible_para(request)
    return {'vendedor_visible': visible, 'vendedor_disponible': visible and coach_configurado()}
