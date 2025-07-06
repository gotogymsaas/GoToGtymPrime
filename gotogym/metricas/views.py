from django.shortcuts import render
from django.contrib.auth import get_user_model
from products.models import Product
from blog.models import Post
from influencer.models import InfluencerProfile

User = get_user_model()

# Puedes agregar más modelos para obtener más métricas

def dashboard(request):
    total_usuarios = User.objects.count()
    total_productos = Product.objects.count()
    total_posts = Post.objects.count()
    influencers_activos = InfluencerProfile.objects.filter(is_active=True).count()
    # Puedes agregar más métricas aquí
    context = {
        'total_usuarios': total_usuarios,
        'total_productos': total_productos,
        'total_posts': total_posts,
        'influencers_activos': influencers_activos,
        # 'total_visitas': ... (si tienes modelo de visitas)
        # 'conversion': ... (si tienes lógica de conversión)
        # 'tareas_completadas': ... (si tienes modelo de tareas)
        # 'ordenes': ... (si tienes modelo de órdenes)
    }
    return render(request, 'metricas/dashboard.html', context)
