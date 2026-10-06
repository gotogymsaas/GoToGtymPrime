from django.urls import path

from . import views

urlpatterns = [
    path('suscribete/', views.suscribete, name='afiliado_suscribete'),
    path('dashboard/', views.dashboard, name='afiliado_dashboard'),
    path('compras-referidas/', views.compras_referidas, name='afiliado_compras_referidas'),
    path('perfil/', views.editar_perfil, name='afiliado_editar_perfil'),
    path('cuenta-de-pago/', views.cuenta_de_pago, name='afiliado_cuenta_pago'),
    path('solicitar-comision/', views.solicitar_retiro, name='afiliado_solicitar_retiro'),
    path('quitar-suscripcion/', views.quitar_suscripcion, name='afiliado_quitar_suscripcion'),
]
