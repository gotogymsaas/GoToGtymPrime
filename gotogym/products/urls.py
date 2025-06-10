from django.urls import path
from .views import ProductFormView, CategoryFormView, ProductListView, CategoryListView
app_name = 'products'
urlpatterns = [
    # path("",ProductListView.as_view(),name="list_product",),
    path("", ProductListView.as_view(), name="list_product"),

    path("categorias/",CategoryListView.as_view(),name="list_category",),
    path("agregarProducto/",ProductFormView.as_view(),name="add_product",),
    path("categorias/agregarCategoria/",CategoryFormView.as_view(),name="add_category",
    ),
]

# urlpatterns = [
#     path('agregar/', ProductFormView.as_view(), name='add_product'),
#     path('categorias/agregar/', CategoryFormView.as_view(), name='add_category'),
    
# ]