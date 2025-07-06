from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from .models import Post, Category
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.contrib.admin.views.decorators import staff_member_required
from .forms import PostForm
from .forms_category import CategoryForm
from django.urls import reverse
from django.http import JsonResponse
from django.template.loader import render_to_string

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

@staff_member_required
def dashboard(request):
    q = request.GET.get('q', '')
    posts = Post.objects.all()
    if q:
        posts = posts.filter(title__icontains=q)
    return render(request, 'blog/dashboard.html', {'posts': posts, 'q': q})

@staff_member_required
def add_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('blog:dashboard')}?success=add")
    else:
        form = PostForm()
    return render(request, 'blog/add_post.html', {'form': form})

@staff_member_required
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, 'blog/category_modal_success.html')
    else:
        form = CategoryForm()
    return render(request, 'blog/category_modal.html', {'form': form})

def categorias_dashboard(request):
    categorias_list = Category.objects.all().order_by('name')

    # Detectar el tamaño de página desde GET o usar un valor por defecto
    try:
        page_size = int(request.GET.get('page_size', 10))
        if page_size < 1 or page_size > 100:
            page_size = 10
    except (TypeError, ValueError):
        page_size = 10

    paginator = Paginator(categorias_list, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'blog/categorias_dashboard.html', {
        'categorias': page_obj,
        'page_obj': page_obj,
        'page_size': page_size
    })

def editar_categoria(request, pk):
    categoria = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            categoria.nombre = nombre
            categoria.save()
            return redirect(reverse('blog:categorias_dashboard'))
    return render(request, 'blog/editar_categoria.html', {'categoria': categoria})

def eliminar_categoria(request, pk):
    categoria = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        categoria.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Devolver fragmento actualizado para AJAX
            categorias_list = Category.objects.all().order_by('name')
            page_size = int(request.GET.get('page_size', 10)) if request.GET.get('page_size') else 10
            paginator = Paginator(categorias_list, page_size)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            tbody_html = render_to_string('blog/_categorias_tbody.html', {'categorias': page_obj})
            return JsonResponse({'tbody': tbody_html})
        return redirect(reverse('blog:categorias_dashboard'))
    return render(request, 'blog/eliminar_categoria.html', {'categoria': categoria})

def crear_categoria(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            from .models import Category
            Category.objects.create(name=nombre)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                # Devolver fragmento actualizado para AJAX
                categorias_list = Category.objects.all().order_by('name')
                page_size = int(request.GET.get('page_size', 10)) if request.GET.get('page_size') else 10
                paginator = Paginator(categorias_list, page_size)
                page_number = request.GET.get('page')
                page_obj = paginator.get_page(page_number)
                tbody_html = render_to_string('blog/_categorias_tbody.html', {'categorias': page_obj})
                return JsonResponse({'tbody': tbody_html})
            from django.urls import reverse
            from django.shortcuts import redirect
            return redirect(reverse('blog:categorias_dashboard'))
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Nombre requerido'}, status=400)
    return redirect('blog:categorias_dashboard')

@staff_member_required
def edit_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            return redirect(f"{reverse('blog:dashboard')}?success=edit")
    else:
        form = PostForm(instance=post)
    return render(request, 'blog/edit_post.html', {'form': form, 'post': post})

@staff_member_required
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        post.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('blog:dashboard')
    return render(request, 'blog/dashboard.html')

def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True)
    return render(request, 'blog/post_detail.html', {'post': post})
