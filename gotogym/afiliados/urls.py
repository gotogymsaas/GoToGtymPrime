from django.urls import path

from . import views

urlpatterns = [
    path('terminos/', views.terminos, name='afiliado_terminos'),
    path('suscribete/', views.suscribete, name='afiliado_suscribete'),
    path('dashboard/', views.dashboard, name='afiliado_dashboard'),
    path('compras-referidas/', views.compras_referidas, name='afiliado_compras_referidas'),
    path('perfil/', views.editar_perfil, name='afiliado_editar_perfil'),
    path('cuenta-de-pago/', views.cuenta_de_pago, name='afiliado_cuenta_pago'),
    path('pagos/', views.pagos, name='afiliado_pagos'),
    path('solicitar-comision/', views.solicitar_retiro, name='afiliado_solicitar_retiro'),
    path('quitar-suscripcion/', views.quitar_suscripcion, name='afiliado_quitar_suscripcion'),
    path('cancelar-baja/', views.cancelar_aviso_de_baja, name='afiliado_cancelar_baja'),
    path('aceptar-terminos/', views.aceptar_terminos, name='afiliado_aceptar_terminos'),
    path('recursos/', views.recursos, name='afiliado_recursos'),
    path('recursos/<int:pk>/descargar/', views.descargar_recurso, name='afiliado_recurso_descargar'),
]
