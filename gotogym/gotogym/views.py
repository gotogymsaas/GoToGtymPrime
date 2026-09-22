from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from blog.models import Post
from django.contrib.auth import get_user_model
from django.db.models.functions import TruncMonth
from django.db.models import Count
from tienda.catalog import curated_product_cards
import json

def home(request):
    # La home publica es la puerta de entrada para visitantes. Con sesion
    # activa no aporta nada (sus unicas acciones son iniciar sesion y crear
    # cuenta), asi que se redirige a la home de sesion. Resolverlo aqui y no
    # en cada plantilla cubre tambien el logo, el menu movil y una URL
    # escrita a mano.
    if request.user.is_authenticated:
        return redirect('logged_home')
    return render(request, 'home.html')

@login_required
def logged_home(request):
    # El Home utiliza la misma fuente de verdad del catalogo que la PLP. De
    # este modo precio, variantes, imagen y disponibilidad no divergen entre
    # la portada y la tienda, y las relaciones se resuelven sin consultas N+1.
    context = {
        'featured_cards': curated_product_cards(limit=4),
        'latest_posts': (
            Post.objects.filter(is_published=True)
            .select_related('category', 'author')
            .order_by('-published')[:3]
        ),
    }
    return render(request, 'logged_home.html', context)

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
    post_stats = (
        Post.objects.annotate(month=TruncMonth('published'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    chart_labels = [p['month'].strftime('%b %Y') for p in post_stats]
    chart_data = [p['count'] for p in post_stats]
    context = {
        'posts': posts,
        'users_count': users_count,
        'visitas': visitas,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'dashboard.html', context)


def pedidos(request):
    return redirect('carrito:cart_detail')


def bienestar(request):
    return redirect('blog:post_list')


def gestion(request):
    return redirect('contacto')


def tecnologia(request):
    return redirect('metricas:metricas_dashboard')


def acerca_de(request):
    return render(request, 'static_pages/about.html')


def contacto(request):
    back_url = reverse('home')
    if request.GET.get('next') == 'logged_home' and request.user.is_authenticated:
        back_url = reverse('logged_home')
    return render(request, 'static_pages/contacto.html', {'back_url': back_url})


@login_required
def politicas_privacidad_usuario(request):
    return render(request, 'static_pages/politicas_privacidad_usuario.html')


def politica_privacidad(request):
    return render(request, 'static_pages/simple_page.html', {
        'title': 'Politica de privacidad',
        'subtitle': 'Protegemos tus datos y los tratamos bajo principios de seguridad y transparencia.',
    })


def terminos(request):
    return render(request, 'accounts/terms_and_conditions.html')


def _policy_page(request, title, paragraphs):
    """Pagina de politica con contenido MOCK: mismo aviso y misma
    plantilla para todas, claramente marcado como provisional."""
    return render(request, 'static_pages/policy_page.html', {'title': title, 'paragraphs': paragraphs})


def politica_cambios(request):
    return _policy_page(request, 'Cambios', [
        'Puedes solicitar un cambio de talla o color dentro de los 15 dias calendario '
        'siguientes a la entrega, siempre que la prenda conserve sus etiquetas originales '
        'y no haya sido usada.',
        'Para iniciar un cambio, escribenos desde la seccion de contacto indicando tu numero '
        'de pedido. Este contenido es un texto de referencia (MOCK) y sera reemplazado por la '
        'politica definitiva de GoToGym antes de operar con clientes reales.',
    ])


def politica_devoluciones(request):
    return _policy_page(request, 'Devoluciones', [
        'Si tu pedido llega con un defecto de fabricacion o no corresponde a lo solicitado, '
        'puedes solicitar su devolucion dentro de los 5 dias habiles siguientes a la entrega.',
        'El valor se reintegra por el mismo medio de pago una vez verificado el estado de la '
        'prenda. Este contenido es un texto de referencia (MOCK) y sera reemplazado por la '
        'politica definitiva antes de operar con clientes reales.',
    ])


def politica_garantia(request):
    return _policy_page(request, 'Garantia', [
        'Las prendas GoToGym cuentan con garantia por defectos de fabricacion durante los 3 '
        'meses siguientes a la compra, bajo condiciones normales de uso y cuidado.',
        'Este contenido es un texto de referencia (MOCK) y sera reemplazado por la politica '
        'definitiva antes de operar con clientes reales.',
    ])


def politica_tratamiento_datos(request):
    return _policy_page(request, 'Tratamiento de datos personales', [
        'GoToGym trata los datos personales suministrados durante el registro y la compra '
        'unicamente para gestionar el pedido, la atencion al cliente y las comunicaciones que '
        'el usuario autorice.',
        'Este contenido es un texto de referencia (MOCK) y sera reemplazado por la politica '
        'definitiva antes de operar con clientes reales.',
    ])


def politica_envios(request):
    return _policy_page(request, 'Envios', [
        'Los tiempos y costos de envio se calculan segun la ciudad de entrega y se muestran '
        'antes de confirmar el pedido.',
        'Este contenido es un texto de referencia (MOCK); el proveedor de envio real todavia '
        'no esta integrado.',
    ])


def politica_pagos(request):
    return _policy_page(request, 'Pagos', [
        'GoToGym SHOP procesa los pagos a traves de un proveedor simulado mientras se completa '
        'la integracion con un proveedor de pagos real. Ningun dato de tarjeta se solicita ni '
        'se almacena.',
        'Este contenido es un texto de referencia (MOCK) y sera reemplazado antes de procesar '
        'pagos reales de clientes.',
    ])
