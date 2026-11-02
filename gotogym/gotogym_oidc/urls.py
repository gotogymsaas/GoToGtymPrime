from django.urls import path

from . import views

app_name = 'gotogym_oidc'

urlpatterns = [
    path('start/', views.start, name='start'),
    path('callback/', views.callback, name='callback'),
    path('link/', views.link_account, name='link'),
    path('logout/', views.logout_view, name='logout'),
]

