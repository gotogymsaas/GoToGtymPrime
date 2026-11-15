from django.urls import path

from . import atencion_humana, consentimiento, personalizacion, privacidad, views

app_name = 'vendedor'

urlpatterns = [
    path('mensaje/', views.mensaje, name='mensaje'),
    path('estado/', views.identidad_estado, name='identidad_estado'),
    path('consentimiento/', consentimiento.consentimiento, name='consentimiento'),
    path('personalizacion/permisos/', personalizacion.guardar_permisos, name='personalizacion_permisos'),
    path('personalizacion/conclusiones/', personalizacion.guardar_conclusiones, name='personalizacion_conclusiones'),
    path('personalizacion/todo/', personalizacion.guardar_todo, name='personalizacion_todo'),
    path('personalizacion/medidas/', personalizacion.guardar_medidas, name='personalizacion_medidas'),
    path('personalizacion/memoria/olvidar/', personalizacion.olvidar_memoria, name='personalizacion_olvidar'),
    path('personalizacion/recordar/', personalizacion.recordar, name='personalizacion_recordar'),
    path('personalizacion/recibo/', privacidad.recibo, name='privacy_receipt'),
    path('personalizacion/revocar-todo/', privacidad.revocar_todo, name='privacy_revoke_all'),
    path('atencion/', atencion_humana.solicitar, name='atencion'),
]
