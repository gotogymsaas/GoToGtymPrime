from django.apps import AppConfig


class VendedorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vendedor'
    verbose_name = 'Vendedor de IA'

    def ready(self):
        # Al crear un perfil, la personalizacion con Quantum Coach empieza activa.
        from accounts.signals import perfil_creado

        from .consentimiento import al_crear_perfil

        perfil_creado.connect(al_crear_perfil, dispatch_uid='vendedor_personalizacion_al_crear_perfil')
