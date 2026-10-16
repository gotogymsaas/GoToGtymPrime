from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import get_language, gettext
from django.utils.translation import gettext as _
from tienda.catalog import curated_product_cards

from . import politicas_contenido as politicas_es
from . import politicas_contenido_en as politicas_en
from .seo import contexto_seo


def home(request):
    # Portada unica para visitantes y compradores: el catalogo y el Journal se
    # pueden explorar sin cuenta (el Journal tiene su acceso en el menu), y el login se pide solo al comprar o al
    # entrar a un panel. Usa la misma fuente de verdad del catalogo que la
    # PLP, de modo que precio, variantes, imagen y disponibilidad no divergen
    # entre la portada y la tienda, y las relaciones se resuelven sin
    # consultas N+1.
    context = {
        'featured_cards': curated_product_cards(limit=4),
    }
    sitio = request.build_absolute_uri('/')
    context.update(contexto_seo(
        'GoToGym: Wear the intelligence',
        gettext(
            'Ropa deportiva con tecnología textil. Explora la colección GoToGym, diseñada para entrenar, '
            'moverte y avanzar a tu manera.'
        ),
        datos=[
            {
                '@context': 'https://schema.org', '@type': 'Organization', 'name': 'GoToGym',
                'url': sitio,
                'logo': request.build_absolute_uri(static('images/logo-gotogym-symbol-transparent.png')),
                'email': 'support@gotogym.store',
            },
            {
                '@context': 'https://schema.org', '@type': 'WebSite', 'name': 'GoToGym', 'url': sitio,
                'potentialAction': {
                    '@type': 'SearchAction',
                    'target': request.build_absolute_uri(reverse('tienda:producto_list')) + '?filtro={search_term_string}',
                    'query-input': 'required name=search_term_string',
                },
            },
        ],
    ))
    return render(request, 'logged_home.html', context)


def healthz(request):
    return HttpResponse('OK')


def acerca_de(request):
    return render(request, 'static_pages/about.html', contexto_seo(
        _('Acerca de GoToGym: marca y ciencia de materiales'),
        _('Propósito y valores de GoToGym y lo que dice la ciencia sobre el grafeno '
          'en la ropa deportiva, con sus fuentes.'),
    ))


def contacto(request):
    context = {'back_url': reverse('home')}
    context.update(contexto_seo(
        gettext('Contacto | GoToGym'),
        gettext('Escríbenos o llámanos: atención sobre compras, productos, personalización y bienestar empresarial.'),
    ))
    return render(request, 'static_pages/contacto.html', context)


@login_required
def politicas_privacidad_usuario(request):
    plantilla = 'static_pages/politicas_privacidad_usuario_en.html' if get_language() == 'en' else 'static_pages/politicas_privacidad_usuario.html'
    return render(request, plantilla)


def politica_privacidad(request):
    return _policy_page(request, 'privacy', 'PRIVACIDAD')


def terminos(request):
    return render(request, 'static_pages/terms_page.html', {
        'policy_key': 'terms',
        'back_url': reverse('home'),
    })


def _policy_page(request, policy_key, nombre):
    """Pagina de politica: misma plantilla para todas; el texto vive en
    `politicas_contenido` (espanol, el original) y `politicas_contenido_en`
    (traduccion de cortesia)."""
    modulo = politicas_en if get_language() == 'en' else politicas_es
    politica = getattr(modulo, nombre)
    return render(request, 'static_pages/policy_page.html', {
        'title': politica['title'],
        'policy_key': policy_key,
        'summary': politica['summary'],
        'sections': politica['sections'],
        'back_url': reverse('home'),
    })


def politica_cambios(request):
    return _policy_page(request, 'changes', 'CAMBIOS')


def politica_devoluciones(request):
    return _policy_page(request, 'returns', 'DEVOLUCIONES')


def politica_garantia(request):
    return _policy_page(request, 'warranty', 'GARANTIA')


def politica_tratamiento_datos(request):
    return _policy_page(request, 'data', 'TRATAMIENTO_DATOS')


def politica_cookies(request):
    return _policy_page(request, 'cookies', 'COOKIES')


def politica_envios(request):
    return _policy_page(request, 'shipping', 'ENVIOS')


def politica_pagos(request):
    return _policy_page(request, 'payments', 'PAGOS')


# Rutas que no tiene sentido indexar: privadas o sin contenido propio.
# 'influencer' es la ruta anterior del programa de afiliados (solo redirige).
RUTAS_NO_INDEXABLES = (
    'admin-panel', 'admin', 'carrito', 'pedidos-tienda', 'pagos', 'accounts',
    'afiliados', 'influencer', 'contabilidad', 'analitica', 'products',
)


def ruta_antigua_de_afiliados(request, resto):
    """/<idioma>/influencer/... -> /<idioma>/afiliados/... (301), con la
    misma cadena de consulta."""
    destino = request.path.replace('/influencer/', '/afiliados/', 1)
    if request.META.get('QUERY_STRING'):
        destino = f"{destino}?{request.META['QUERY_STRING']}"
    return HttpResponsePermanentRedirect(destino)


def robots_txt(request):
    """`robots.txt`: todo es rastreable salvo lo privado, e indica el mapa del
    sitio. Las rutas privadas llevan prefijo de idioma, asi que se listan por
    cada idioma."""
    lineas = ['User-agent: *', 'Allow: /']
    for codigo, _nombre in settings.LANGUAGES:
        lineas.extend(f'Disallow: /{codigo}/{ruta}/' for ruta in RUTAS_NO_INDEXABLES)
    lineas.extend(['Disallow: /api/', 'Disallow: /setlang/', '', f'Sitemap: {request.build_absolute_uri("/sitemap.xml")}', ''])
    return HttpResponse('\n'.join(lineas), content_type='text/plain; charset=utf-8')
