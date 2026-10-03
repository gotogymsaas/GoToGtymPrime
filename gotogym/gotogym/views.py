from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from tienda.catalog import curated_product_cards

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
        'GoToGym: diseñada para tu forma de avanzar',
        'Ropa deportiva con tecnología textil. Explora la colección GoToGym, diseñada para entrenar, '
        'moverte y avanzar a tu manera.',
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
        'Acerca de GoToGym: tecnología y ciencia de materiales',
        'La visión de GoToGym y lo que dice la ciencia sobre el grafeno en la ropa deportiva, '
        'con sus fuentes y el nivel de evidencia de cada beneficio.',
    ))


def contacto(request):
    context = {'back_url': reverse('home')}
    context.update(contexto_seo(
        'Contacto | GoToGym',
        'Escríbenos o llámanos: atención sobre compras, productos, personalización y bienestar empresarial.',
    ))
    return render(request, 'static_pages/contacto.html', context)


@login_required
def politicas_privacidad_usuario(request):
    return render(request, 'static_pages/politicas_privacidad_usuario.html')


def politica_privacidad(request):
    return _policy_page(
        request,
        'Política de privacidad',
        [
            'GoToGym trata la información necesaria para gestionar tu cuenta, tus compras, '
            'la atención al cliente y las comunicaciones que hayas autorizado.',
            'No vendemos tus datos. Puedes solicitar acceso, corrección, actualización o '
            'supresión escribiendo a privacy@gotogym.store.',
        ],
        policy_key='privacy',
        summary='Protegemos tus datos y los tratamos bajo principios de seguridad, transparencia y control por parte del titular.',
        provisional=False,
    )


def terminos(request):
    return render(request, 'static_pages/terms_page.html', {
        'policy_key': 'terms',
        'back_url': reverse('home'),
    })


def _policy_page(request, title, paragraphs, *, policy_key='', summary='', provisional=True):
    """Pagina de politica con contenido MOCK: mismo aviso y misma
    plantilla para todas, claramente marcado como provisional."""
    return render(request, 'static_pages/policy_page.html', {
        'title': title,
        'policy_key': policy_key,
        'summary': summary,
        'provisional': provisional,
        'sections': [{'title': 'Lo que debes saber', 'paragraphs': paragraphs}],
        'back_url': reverse('home'),
    })


def politica_cambios(request):
    return _policy_page(request, 'Cambios', [
        'Puedes solicitar un cambio de talla o color dentro de los 15 dias calendario '
        'siguientes a la entrega, siempre que la prenda conserve sus etiquetas originales '
        'y no haya sido usada.',
        'Para iniciar un cambio, escribenos desde la seccion de contacto indicando tu numero '
        'de pedido. Este contenido es un texto de referencia (MOCK) y sera reemplazado por la '
        'politica definitiva de GoToGym antes de operar con clientes reales.',
    ], policy_key='changes', summary='Cómo solicitar un cambio de talla o color y qué condiciones debe conservar la prenda.')


def politica_devoluciones(request):
    return _policy_page(request, 'Devoluciones', [
        'Si tu pedido llega con un defecto de fabricacion o no corresponde a lo solicitado, '
        'puedes solicitar su devolucion dentro de los 5 dias habiles siguientes a la entrega.',
        'El valor se reintegra por el mismo medio de pago una vez verificado el estado de la '
        'prenda. Este contenido es un texto de referencia (MOCK) y sera reemplazado por la '
        'politica definitiva antes de operar con clientes reales.',
    ], policy_key='returns', summary='Qué hacer si recibes un producto con defecto o diferente al que compraste.')


def politica_garantia(request):
    return _policy_page(request, 'Garantía', [
        'Las prendas GoToGym cuentan con garantia por defectos de fabricacion durante los 3 '
        'meses siguientes a la compra, bajo condiciones normales de uso y cuidado.',
        'Este contenido es un texto de referencia (MOCK) y sera reemplazado por la politica '
        'definitiva antes de operar con clientes reales.',
    ], policy_key='warranty', summary='La cobertura disponible ante posibles defectos de fabricación.')


def politica_tratamiento_datos(request):
    return _policy_page(request, 'Tratamiento de datos personales', [
        'GoToGym trata los datos personales suministrados durante el registro y la compra '
        'unicamente para gestionar el pedido, la atencion al cliente y las comunicaciones que '
        'el usuario autorice.',
        'Este contenido es un texto de referencia (MOCK) y sera reemplazado por la politica '
        'definitiva antes de operar con clientes reales.',
    ], policy_key='data', summary='Las finalidades y principios aplicados a la información que compartes con GoToGym.')


def politica_envios(request):
    return _policy_page(request, 'Envíos', [
        'Los tiempos y costos de envio se calculan segun la ciudad de entrega y se muestran '
        'antes de confirmar el pedido.',
        'Este contenido es un texto de referencia (MOCK); el proveedor de envio real todavia '
        'no esta integrado.',
    ], policy_key='shipping', summary='Cómo se calculan el tiempo y el costo de llevar tu pedido hasta ti.')


def politica_pagos(request):
    return _policy_page(request, 'Pagos', [
        'GoToGym SHOP procesa los pagos a traves de un proveedor simulado mientras se completa '
        'la integracion con un proveedor de pagos real. Ningun dato de tarjeta se solicita ni '
        'se almacena.',
        'Este contenido es un texto de referencia (MOCK) y sera reemplazado antes de procesar '
        'pagos reales de clientes.',
    ], policy_key='payments', summary='Cómo protegemos el proceso de pago y qué información nunca almacenamos.')


# Rutas que no tiene sentido indexar: privadas o sin contenido propio.
RUTAS_NO_INDEXABLES = (
    'admin-panel', 'admin', 'carrito', 'pedidos-tienda', 'pagos', 'accounts',
    'influencer', 'contabilidad', 'analitica', 'products',
)


def robots_txt(request):
    """`robots.txt`: todo es rastreable salvo lo privado, e indica el mapa del
    sitio. Las rutas privadas llevan prefijo de idioma, asi que se listan por
    cada idioma."""
    lineas = ['User-agent: *', 'Allow: /']
    for codigo, _nombre in settings.LANGUAGES:
        lineas.extend(f'Disallow: /{codigo}/{ruta}/' for ruta in RUTAS_NO_INDEXABLES)
    lineas.extend(['Disallow: /api/', 'Disallow: /setlang/', '', f'Sitemap: {request.build_absolute_uri("/sitemap.xml")}', ''])
    return HttpResponse('\n'.join(lineas), content_type='text/plain; charset=utf-8')
