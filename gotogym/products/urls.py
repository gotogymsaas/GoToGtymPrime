from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('add-category/', views.add_category, name='add_category'),
    path('add-product/', views.add_product, name='add_product'),
    path('categories/', views.list_category, name='list_category'),
    path('products/', views.list_product, name='list_product'),
    path('product/<int:pk>/', views.view_product, name='view_product'),
    path('product/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('product/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('delete-image/<int:pk>/', views.delete_product_image, name='delete_product_image'),
    path('category/<int:pk>/edit/', views.edit_category, name='edit_category'),
    path('category/<int:pk>/delete/', views.delete_category, name='delete_category'),
    path('delete-category-ajax/<int:pk>/', views.delete_category_ajax, name='delete_category_ajax'),
    path('category/<int:pk>/', views.view_category, name='view_category'),
    path('brands/', views.brand_list, name='brand_list'),
    path('brands/add/', views.brand_list, name='brand_add'),  # usa el mismo form que listar
    path('brands/<int:pk>/edit/', views.brand_edit, name='brand_edit'),
    path('brands/<int:pk>/preview/', views.brand_preview, name='brand_preview'),
    path('brands/<int:pk>/delete/', views.brand_delete, name='brand_delete'),
]
