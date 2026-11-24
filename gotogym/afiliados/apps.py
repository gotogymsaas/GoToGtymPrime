from django.apps import AppConfig


class AfiliadosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'afiliados'

    def ready(self):
        from orders.senales import pedido_anulado, pedido_cobrado, pedido_entregado

        from . import receptores

        pedido_cobrado.connect(receptores.registrar_comision, dispatch_uid='afiliados.registrar_comision')
        pedido_entregado.connect(
            receptores.iniciar_validacion_de_comision, dispatch_uid='afiliados.iniciar_validacion_de_comision',
        )
        pedido_anulado.connect(receptores.revertir_comision, dispatch_uid='afiliados.revertir_comision')
