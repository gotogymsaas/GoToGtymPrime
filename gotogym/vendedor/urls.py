from django.urls import path

from . import atencion_humana, consentimiento, personalizacion, views

app_name = 'vendedor'

urlpatterns = [
    path('mensaje/', views.mensaje, name='mensaje'),
    path('consentimiento/', consentimiento.consentimiento, name='consentimiento'),
    path('personalizacion/permisos/', personalizacion.guardar_permisos, name='personalizacion_permisos'),
    path('personalizacion/medidas/', personalizacion.guardar_medidas, name='personalizacion_medidas'),
    path('personalizacion/memoria/olvidar/', personalizacion.olvidar_memoria, name='personalizacion_olvidar'),
    path('personalizacion/recordar/', personalizacion.recordar, name='personalizacion_recordar'),
    path('atencion/', atencion_humana.solicitar, name='atencion'),
]
