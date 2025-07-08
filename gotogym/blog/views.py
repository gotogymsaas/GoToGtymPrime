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
from django.contrib.auth.decorators import login_required, user_passes_test

def is_influencer(user):
    return user.is_authenticated and hasattr(user, 'influencer_profile')

def post_list(request):
    user = request.user
    is_authenticated = user.is_authenticated
    is_influencer = is_authenticated and hasattr(user, 'influencer_profile')
    is_admin = is_authenticated and (user.is_staff or user.is_superuser)

    # Todos los usuarios (incluyendo influencers) ven todos los posts publicados
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

    # Set template_extends for conditional base
    if is_admin:
        template_extends = "_base_dasboard.html"
    else:
        template_extends = "base.html"

    context = {
        'posts': page_obj.object_list,
        'categories': categories,
        'authors': authors,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'params': params,
        'is_influencer': is_influencer,
        'is_admin': is_admin,
        'template_extends': template_extends,
        'user': user,
        'is_authenticated': is_authenticated,
    }
    return render(request, 'blog/post_list.html', context)

@staff_member_required
def dashboard(request):
    q = request.GET.get('q', '')
    posts = Post.objects.all()
    if q:
        posts = posts.filter(title__icontains=q)
    return render(request, 'blog/dashboard.html', {'posts': posts, 'q': q})

@login_required
def add_post(request):
    user = request.user
    is_admin = user.is_staff or user.is_superuser
    is_influencer_user = is_influencer(user)
    # Solo permitir añadir si es admin/staff o influencer
    if not is_admin and not is_influencer_user:
        return redirect('blog:post_list')
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            # Asignar autor si es influencer
            if is_influencer_user and not is_admin:
                post.author = user
            post.save()
            if is_admin:
                return redirect(f"{reverse('blog:dashboard')}?success=add")
            elif is_influencer_user:
                return redirect('blog:post_list')
    else:
        if is_influencer_user and not is_admin:
            form = PostForm(initial={'author': user})
            form.fields['author'].disabled = True
        else:
            # Si es admin, mostrar todos los usuarios pero seleccionar por defecto el admin logueado
            form = PostForm(initial={'author': user})
    # Template base según rol
    if is_admin:
        template_extends = "_base_dasboard.html"
    else:
        template_extends = "base.html"
    return render(request, 'blog/add_post.html', {'form': form, 'template_extends': template_extends, 'is_admin': is_admin, 'is_influencer': is_influencer_user, 'user': user})

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

@login_required
def edit_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    user = request.user
    is_admin = user.is_staff or user.is_superuser
    is_influencer_user = is_influencer(user)
    # Solo permitir editar si es admin/staff o si es influencer y es el autor
    if not is_admin and not (is_influencer_user and post.author == user):
        return redirect('blog:post_list')
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        # Influencer solo puede guardar si es el autor
        if is_influencer_user and not is_admin and post.author != user:
            return redirect('blog:post_list')
        if form.is_valid():
            form.save()
            # Redirección según rol
            if is_admin:
                return redirect(f"{reverse('blog:dashboard')}?success=edit")
            elif is_influencer_user:
                return redirect('blog:post_list')
            else:
                return redirect('blog:post_list')
    else:
        form = PostForm(instance=post)
    # Template base según rol
    if is_admin:
        template_extends = "_base_dasboard.html"
    else:
        template_extends = "base.html"
    return render(request, 'blog/edit_post.html', {'form': form, 'post': post, 'template_extends': template_extends, 'is_admin': is_admin, 'is_influencer': is_influencer_user})

@login_required
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    user = request.user
    is_admin = user.is_staff or user.is_superuser
    is_influencer_user = is_influencer(user)
    # Solo permitir eliminar si es admin/staff o si es influencer y es el autor
    if not is_admin and not (is_influencer_user and post.author == user):
        return redirect('blog:post_list')
    # Template base según rol
    if is_admin:
        template_extends = "_base_dasboard.html"
    else:
        template_extends = "base.html"
    if request.method == 'POST':
        post.delete()
        if is_influencer_user and not is_admin:
            return redirect('blog:post_list')
        return redirect('blog:dashboard')
    return render(request, 'blog/delete_post.html', {'post': post, 'template_extends': template_extends, 'is_admin': is_admin, 'is_influencer': is_influencer_user})

def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True)
    return render(request, 'blog/post_detail.html', {'post': post})
