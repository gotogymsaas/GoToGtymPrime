from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="admin_dashboard"),
    path("productos/", views.products_list, name="admin_products"),
    path("productos/nuevo/", views.product_edit, name="admin_product_new"),
    path("productos/<int:pk>/editar/", views.product_edit, name="admin_product_edit"),
    path("productos/<int:pk>/eliminar/", views.product_delete, name="admin_product_delete"),
    path("productos/<int:pk>/imagen/eliminar/", views.product_image_delete, name="admin_product_image_delete"),
    path("productos/<int:pk>/media/agregar/", views.product_media_add, name="admin_product_media_add"),
    path("productos/<int:pk>/media/<int:media_id>/eliminar/", views.product_media_delete, name="admin_product_media_delete"),
    path("productos/<int:pk>/media/reordenar/", views.product_media_reorder, name="admin_product_media_reorder"),
    path("variantes/", views.variants_list, name="admin_variants"),
    path("variantes/<int:pk>/stock/", views.variant_stock_update, name="admin_variant_stock_update"),
    path("variantes/umbral/", views.inventory_threshold_update, name="admin_inventory_threshold_update"),
    path("pedidos/", views.orders_list, name="admin_orders"),
    path("pedidos/<str:order_number>/", views.order_detail, name="admin_order_detail"),
    path("pedidos/<str:order_number>/estado/", views.order_update_status, name="admin_order_update_status"),
    path("usuarios/", views.users_list, name="admin_users"),
    path("usuarios/<int:pk>/rol/", views.user_role_update, name="admin_user_role_update"),
    path("usuarios/<int:pk>/estado/", views.user_toggle_active, name="admin_user_toggle_active"),
    path("usuarios/<int:pk>/eliminar/", views.user_delete, name="admin_user_delete"),
    path("usuarios/<int:pk>/grupos/", views.user_groups_update, name="admin_user_groups_update"),
    path("catalogos/", views.catalogs, name="admin_catalogs"),
    path("catalogos/categorias/<int:pk>/eliminar/", views.category_delete, name="admin_category_delete"),
    path("catalogos/marcas/<int:pk>/eliminar/", views.brand_delete, name="admin_brand_delete"),
    path("catalogos/etiquetas/<int:pk>/estado/", views.tag_toggle, name="admin_tag_toggle"),
    path("catalogos/etiquetas/<int:pk>/eliminar/", views.tag_delete, name="admin_tag_delete"),
    path("cupones/", views.coupons_list, name="admin_coupons"),
    path("cupones/nuevo/", views.coupon_edit, name="admin_coupon_new"),
    path("cupones/<int:pk>/editar/", views.coupon_edit, name="admin_coupon_edit"),
    path("cupones/<int:pk>/estado/", views.coupon_toggle, name="admin_coupon_toggle"),
    path("cupones/<int:pk>/eliminar/", views.coupon_delete, name="admin_coupon_delete"),
    # "Grupos y permisos" se retira temporalmente de la interfaz (no se va a
    # usar en esta etapa): el enlace de navegacion ya no aparece en
    # administracion/base.html. Las rutas se dejan activas (no solo la
    # logica) para que las vistas sigan siendo funcionales de punta a
    # punta -- incluidos sus propios `redirect("admin_groups")` -- el dia
    # que se reactive el enlace; nada aqui se ejecuta si nadie navega hasta
    # esta URL a mano.
    path("grupos/", views.groups_list, name="admin_groups"),
    path("grupos/nuevo/", views.group_edit, name="admin_group_new"),
    path("grupos/<int:pk>/editar/", views.group_edit, name="admin_group_edit"),
    path("grupos/<int:pk>/eliminar/", views.group_delete, name="admin_group_delete"),
]
