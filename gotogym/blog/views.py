from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext
from gotogym.seo import contexto_seo, url_absoluta

from .models import Category, Post


def post_list(request):
    posts = Post.objects.filter(is_published=True).select_related('category', 'author').order_by('-published')
    has_published_posts = posts.exists()
    categories = Category.objects.all()

    search = request.GET.get('search', '')
    category = request.GET.get('category', '')

    if search:
        posts = posts.filter(Q(title__icontains=search) | Q(content__icontains=search))
    if category:
        posts = posts.filter(category_id=category)

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
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'params': params,
        'has_published_posts': has_published_posts,
        'has_active_filters': any([search, category]),
    }
    context.update(contexto_seo(
        gettext('GoToGym Journal: historias para avanzar'),
        gettext(
            'Diseño, rendimiento, tecnología textil y bienestar: ciencia de materiales y ropa deportiva '
            'explicadas con sus fuentes.'
        ),
    ))
    return render(request, 'blog/post_list.html', context)


def post_detail(request, slug):
    post = get_object_or_404(
        Post.objects.select_related('category', 'author').filter(is_published=True),
        slug=slug,
    )
    related_posts = (
        Post.objects.filter(is_published=True, category=post.category)
        .exclude(id=post.id)
        .order_by('-published')[:3]
    )
    imagen = url_absoluta(request, post.featured.url) if post.featured else None
    datos = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': post.titulo,
        'datePublished': post.published.isoformat(),
        'dateModified': post.updated.isoformat(),
        'author': {'@type': 'Organization', 'name': post.firma},
        'publisher': {'@type': 'Organization', 'name': 'GoToGym'},
        'mainEntityOfPage': request.build_absolute_uri(request.path),
    }
    if post.reference_items:
        datos['citation'] = [ref['text'] for ref in post.reference_items]
    if imagen:
        datos['image'] = imagen
    context = {'post': post, 'related_posts': related_posts}
    context.update(contexto_seo(
        f'{post.titulo} | GoToGym Journal', post.resumen or post.cuerpo, tipo='article', imagen=imagen, datos=datos,
    ))
    return render(request, 'blog/post_detail.html', context)
