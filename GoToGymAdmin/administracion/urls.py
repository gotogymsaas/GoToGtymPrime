from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="admin_dashboard"),
    path("productos/", views.products_list, name="admin_products"),
    path("productos/nuevo/", views.product_edit, name="admin_product_new"),
    path("productos/<int:pk>/editar/", views.product_edit, name="admin_product_edit"),
    path("productos/<int:pk>/eliminar/", views.product_delete, name="admin_product_delete"),
    path("productos/<int:pk>/imagen/eliminar/", views.product_image_delete, name="admin_product_image_delete"),
    path("usuarios/", views.users_list, name="admin_users"),
    path("catalogos/", views.catalogs, name="admin_catalogs"),
    path("catalogos/categorias/<int:pk>/eliminar/", views.category_delete, name="admin_category_delete"),
    path("catalogos/marcas/<int:pk>/eliminar/", views.brand_delete, name="admin_brand_delete"),
]
