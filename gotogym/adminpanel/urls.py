# from django.urls import path
# from . import views

# app_name = 'adminpanel'

# urlpatterns = [
#     path('', views.dashboard, name='dashboard'),
#     path('agregar/', views.agregar_post, name='agregar_post'),
#     path('editar/<int:post_id>/', views.editar_post, name='editar_post'),
#     # path('eliminar/<int:post_id>/', views.eliminar_post, name='eliminar_post'),
#     path('post/<int:post_id>/eliminar/', views.eliminar_post, name='eliminar_post'),
# ]

from django.urls import path
from blog import views as blog

app_name = 'adminpanel'

urlpatterns = [
    path('', blog.dashboard, name='dashboard'),

]
