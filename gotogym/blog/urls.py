from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    path('add/', views.add_post, name='add_post'),
    path('add-category/', views.add_category, name='add_category'),
    path('categorias/', views.categorias_dashboard, name='categorias_dashboard'),
    path('categorias/crear/', views.crear_categoria, name='crear_categoria'),
    path('categorias/<int:pk>/editar/', views.editar_categoria, name='editar_categoria'),
    path('categorias/<int:pk>/eliminar/', views.eliminar_categoria, name='eliminar_categoria'),
    path('edit/<int:pk>/', views.edit_post, name='edit_post'),
    path('delete/<int:pk>/', views.delete_post, name='delete_post'),
    path('<slug:slug>/', views.post_detail, name='post_detail'),  # Detalle del post
]
