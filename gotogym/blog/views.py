from django.shortcuts import render
from django.core.paginator import Paginator
from .models import Post, Category
from django.contrib.auth import get_user_model
from django.db.models import Q

def post_list(request):
    posts = Post.objects.filter(is_published=True).select_related('category', 'author').order_by('-published')
    categories = Category.objects.all()
    authors = get_user_model().objects.filter(posts__isnull=False).distinct()

    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    author = request.GET.get('author', '')

    if search:
        posts = posts.filter(Q(title__icontains=search) | Q(content__icontains=search))
    if category:
        posts = posts.filter(category_id=category)
    if author:
        posts = posts.filter(author_id=author)

    paginator = Paginator(posts, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    params = request.GET.copy()
    if 'page' in params:
        params.pop('page')
    params = params.urlencode()

    context = {
        'posts': page_obj.object_list,
        'categories': categories,
        'authors': authors,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'params': params,
    }
    return render(request, 'blog/post_list.html', context)
