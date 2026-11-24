from django.urls import path

from . import views

# Se monta bajo el prefijo del panel (`administracion.urls`). Los nombres no
# llevan espacio de nombres, igual que el resto de rutas del panel.
urlpatterns = [
    path('', views.lista, name='admin_tareas'),
    path('<int:pk>/reintentar/', views.reintentar, name='admin_tarea_reintentar'),
]
