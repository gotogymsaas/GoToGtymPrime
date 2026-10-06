from django.urls import path

from . import views

urlpatterns = [
    path('suscribete/', views.suscribete, name='influencer_suscribete'),
    path('dashboard/', views.dashboard, name='influencer_dashboard'),
    path('compras-referidas/', views.compras_referidas, name='influencer_compras_referidas'),
    path('perfil/', views.editar_perfil, name='influencer_editar_perfil'),
    path('cuenta-de-pago/', views.cuenta_de_pago, name='influencer_cuenta_pago'),
    path('solicitar-comision/', views.solicitar_retiro, name='influencer_solicitar_retiro'),
    path('quitar-suscripcion/', views.quitar_suscripcion, name='influencer_quitar_suscripcion'),
]
