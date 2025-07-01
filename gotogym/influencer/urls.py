from django.urls import path
from . import views

urlpatterns = [
    path('suscribete/', views.suscribete, name='influencer_suscribete'),
    path('dashboard/', views.dashboard, name='influencer_dashboard'),
    path('compras-referidas/', views.compras_referidas, name='influencer_compras_referidas'),
    path('solicitar-retiro/', views.solicitar_retiro, name='influencer_solicitar_retiro'),
    path('quitar-suscripcion/', views.quitar_suscripcion, name='influencer_quitar_suscripcion'),
]
