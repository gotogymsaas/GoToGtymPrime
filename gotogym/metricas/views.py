from django.shortcuts import render
from django.contrib.auth import get_user_model
from products.models import Product
from blog.models import Post
from influencer.models import InfluencerProfile
from django.db.models import Count, Q

User = get_user_model()

def dashboard(request):
    # Usuarios por rol
    total_usuarios = User.objects.count()
    total_admins = User.objects.filter(is_staff=True, is_superuser=False, influencer_profile__isnull=True).count()
    total_influencers = InfluencerProfile.objects.filter(user__is_staff=False, user__is_superuser=False).count()
    total_admins_influencers = User.objects.filter(is_staff=True, influencer_profile__isnull=False).count()
    total_superusers = User.objects.filter(is_superuser=True).count()
    total_usuarios_normales = User.objects.filter(is_staff=False, is_superuser=False, influencer_profile__isnull=True).count()

    # Publicaciones por rol
    total_posts = Post.objects.count()
    posts_por_influencers = Post.objects.filter(author__influencer_profile__isnull=False, author__is_staff=False, author__is_superuser=False).count()
    posts_por_admins = Post.objects.filter(author__is_staff=True, author__influencer_profile__isnull=True, author__is_superuser=False).count()
    posts_por_admins_influencers = Post.objects.filter(author__is_staff=True, author__influencer_profile__isnull=False, author__is_superuser=False).count()
    posts_por_superusers = Post.objects.filter(author__is_superuser=True).count()
    posts_publicados = Post.objects.filter(is_published=True).count()

    # Productos
    total_productos = Product.objects.count()
    productos_destacados = Product.objects.filter(featured=True).count()
    productos_sin_stock = Product.objects.filter(stock=0).count()

    context = {
        'total_usuarios': total_usuarios,
        'total_admins': total_admins,
        'total_influencers': total_influencers,
        'total_admins_influencers': total_admins_influencers,
        'total_superusers': total_superusers,
        'total_usuarios_normales': total_usuarios_normales,
        'total_posts': total_posts,
        'posts_por_influencers': posts_por_influencers,
        'posts_por_admins': posts_por_admins,
        'posts_por_admins_influencers': posts_por_admins_influencers,
        'posts_por_superusers': posts_por_superusers,
        'posts_publicados': posts_publicados,
        'total_productos': total_productos,
        'productos_destacados': productos_destacados,
        'productos_sin_stock': productos_sin_stock,
    }
    return render(request, 'metricas/dashboard.html', context)
