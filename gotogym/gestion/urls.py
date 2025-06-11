from django.urls import path
from .views import BlogView, TallaView, HomeView,ViewView, RoleBasedRedirectView, AdminView, UserView


urlpatterns = [
    # path("", HomeView.as_view(), name="home"),
    path("index", ViewView.as_view(), name="gestion_index"),
    path("redirect/", RoleBasedRedirectView.as_view(), name="role_redirect"),
    path("admin-view/", AdminView.as_view(), name="admin_view"),
    path("user-view/", UserView.as_view(), name="user_view"),
    path("talla/", TallaView.as_view(), name="talla"),
    path("blog/", BlogView.as_view(), name="blog"),
    

]
