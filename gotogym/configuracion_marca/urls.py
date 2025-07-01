from django.urls import path
from . import views

app_name = 'configuracion_marca'

urlpatterns = [
    path('', views.paleta, name='paleta'),
    path('editar/<int:pk>/', views.editar_color, name='editar_color'),
]
