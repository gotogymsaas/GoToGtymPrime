<<<<<<< HEAD
from django.db.models import Q
from django.views.generic import ListView, DetailView
from django.contrib.auth import get_user_model

from .models import Post, Category

User = get_user_model()

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from .forms import PostForm
from django.contrib import messages

def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)

@superuser_required
def dashboard(request):
    query = request.GET.get("q", "")
    posts = Post.objects.all().order_by("published")

    if query:
        posts = posts.filter(Q(title__icontains=query))

    paginator   = Paginator(posts, 4)
    page_number = request.GET.get("page")
    page_obj    = paginator.get_page(page_number)
    context = {
        "posts": page_obj.object_list,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
    }

    return render( request, "blog/dashboard.html", context    )

@superuser_required
def agregar_post(request):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect("blog:dashboard")
    else:
        form = PostForm()
    return render(request, "blog/agregar_post.html", {"form": form})

@superuser_required
def editar_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)   #  <<<<<<
        if form.is_valid():
            form.save()
            return redirect("blog:dashboard")
    else:
        form = PostForm(instance=post)
    return render(request, "blog/editar_post.html", {"form": form, "post": post})

@superuser_required
def eliminar_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == "POST":
        post.delete()
        messages.success(request, "Publicación eliminada correctamente.")
    return redirect('blog:dashboard')

def preview_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'blog/preview_post.html', {'post': post})

class PostListView(ListView):
    model               = Post
    template_name       = "blog/post_list.html"
    context_object_name = "posts"
    paginate_by         = 9

    def get_queryset(self):
        qs = Post.objects.all()

        search   = self.request.GET.get("search", "").strip()
        category = self.request.GET.get("category", "")
        author   = self.request.GET.get("author", "")

        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(body__icontains=search)  |
                Q(excerpt__icontains=search)
            )

        if category:
            qs = qs.filter(category_id=category)

        if author:
            qs = qs.filter(author_id=author)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.all()
        ctx["authors"]    = User.objects.filter(post__isnull=False).distinct()
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["params"] = params.urlencode()
        return ctx


class PostDetailView(DetailView):
    model               = Post
    template_name       = "blog/post_detail.html"
    context_object_name = "post"
=======
from django.db.models import Q
from django.views.generic import ListView, DetailView
from django.contrib.auth import get_user_model

from .models import Post, Category

User = get_user_model()

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from .forms import PostForm
from django.contrib import messages

def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)

@superuser_required
def dashboard(request):
    query = request.GET.get("q", "")
    posts = Post.objects.all().order_by("published")

    if query:
        posts = posts.filter(Q(title__icontains=query))

    paginator   = Paginator(posts, 4)
    page_number = request.GET.get("page")
    page_obj    = paginator.get_page(page_number)
    context = {
        "posts": page_obj.object_list,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
    }

    return render( request, "blog/dashboard.html", context    )

@superuser_required
def agregar_post(request):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect("blog:dashboard")
    else:
        form = PostForm()
    return render(request, "blog/agregar_post.html", {"form": form})

@superuser_required
def editar_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)   #  <<<<<<
        if form.is_valid():
            form.save()
            return redirect("blog:dashboard")
    else:
        form = PostForm(instance=post)
    return render(request, "blog/editar_post.html", {"form": form, "post": post})

@superuser_required
def eliminar_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == "POST":
        post.delete()
        messages.success(request, "Publicación eliminada correctamente.")
    return redirect('blog:dashboard')

def preview_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'blog/preview_post.html', {'post': post})

class PostListView(ListView):
    model               = Post
    template_name       = "blog/post_list.html"
    context_object_name = "posts"
    paginate_by         = 9

    def get_queryset(self):
        qs = Post.objects.all()

        search   = self.request.GET.get("search", "").strip()
        category = self.request.GET.get("category", "")
        author   = self.request.GET.get("author", "")

        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(body__icontains=search)  |
                Q(excerpt__icontains=search)
            )

        if category:
            qs = qs.filter(category_id=category)

        if author:
            qs = qs.filter(author_id=author)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.all()
        ctx["authors"]    = User.objects.filter(post__isnull=False).distinct()
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["params"] = params.urlencode()
        return ctx


class PostDetailView(DetailView):
    model               = Post
    template_name       = "blog/post_detail.html"
    context_object_name = "post"
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
