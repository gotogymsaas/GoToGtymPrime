from django.urls import path

from . import views
from .feeds import JournalFeed

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('feed/', JournalFeed(), name='feed'),
    path('<slug:slug>/', views.post_detail, name='post_detail'),
]
