<<<<<<< HEAD
=======
# blog/urls.py
# blog/urls.py
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
# from django.urls import path
# from .views import PostListView, PostDetailView, CategoryListView

# app_name = "blog"

# urlpatterns = [
#     path("",              PostListView.as_view(),      name="home"),
#     path("<slug:slug>/",  PostDetailView.as_view(),    name="detail"),
#     path("categoria/<slug:slug>/", CategoryListView.as_view(), name="category"),
# ]
from django.urls import path
from .views import PostListView, PostDetailView
from . import views

app_name = "blog"

urlpatterns = [
    path("",                PostListView.as_view(), name="post_list"),
    path('adminpanel/', views.dashboard, name='dashboard'),
    path('agregar/', views.agregar_post, name='agregar_post'),
    path('editar/<int:post_id>/', views.editar_post, name='editar_post'),
    path('post/<int:post_id>/eliminar/', views.eliminar_post, name='eliminar_post'),
<<<<<<< HEAD
    path('post/<int:post_id>/preview/', views.preview_post, name='preview_post'),  
    path("<slug:slug>/",    PostDetailView.as_view(), name="post_detail"),

]

=======
    path('post/<int:post_id>/preview/', views.preview_post, name='preview_post'),  # Vista previa
    path("<slug:slug>/",    PostDetailView.as_view(), name="post_detail"),

]
# blog/urls.py
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01

