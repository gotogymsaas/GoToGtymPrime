from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from blog.models import Post
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncMonth
from django.db.models import Count
import json
from web.models import TemplateConfig

def home(request):
    config = TemplateConfig.objects.filter(template_name='home').first()
    color = config.color if config else '#C5A46B'
    image = config.image.url if config and config.image else None
    font = config.font if config else ''
    show_influencer_modal = False
    if request.user.is_authenticated and hasattr(request.user, 'show_influencer_modal') and request.user.show_influencer_modal:
        show_influencer_modal = True
        request.user.show_influencer_modal = False
        request.user.save(update_fields=["show_influencer_modal"])
    return render(request, 'home.html', {
        'color': color,
        'image': image,
        'font': font,
        "show_influencer_modal": show_influencer_modal
    })

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def dashboard(request):
    q = request.GET.get('q', '')
    posts = Post.objects.all()
    if q:
        posts = posts.filter(title__icontains=q)
    users_count = get_user_model().objects.count()
    visitas = 0  # Puedes conectar aquí tu sistema de visitas si lo tienes
    # Gráfica: publicaciones por mes
    try:
        post_stats = (
            Post.objects.annotate(month=TruncMonth('published'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        chart_labels = [p['month'].strftime('%b %Y') for p in post_stats if p['month']]
        chart_data = [p['count'] for p in post_stats if p['month']]
    except Exception as e:
        chart_labels = []
        chart_data = []
    context = {
        'posts': posts,
        'users_count': users_count,
        'visitas': visitas,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'dashboard.html', context)
