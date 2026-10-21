"""
URL configuration for gotogym project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import URLPattern, URLResolver, include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.shortcuts import redirect
from django.urls import URLPattern, URLResolver, include, path
from django.views.generic import RedirectView
from django.views.i18n import set_language
from django.views.static import serve
from payments import views as payments_views

from . import views
from .sitemaps import SITEMAPS

urlpatterns: list[URLPattern | URLResolver] = [
    path('accounts', lambda request: redirect('commercial_login', permanent=False)),
    path('setlang/', set_language, name='set_language'),
    path('healthz', views.healthz, name='healthz'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('crm/healthz', views.healthz, name='legacy_crm_healthz'),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    path('products/products/', RedirectView.as_view(pattern_name='tienda:producto_list', permanent=False), name='legacy_products_products'),
    # Fuera de i18n_patterns a proposito: un webhook real no antepone un
    # prefijo de idioma a la URL.
    path('pagos/webhook/mercadopago/', payments_views.mercadopago_webhook, name='mercadopago_webhook'),
]

urlpatterns += i18n_patterns(
    path('', views.home, name='home'),
    # Alias de la antigua portada con sesion: ahora es la misma de '/'.
    path('welcome/', RedirectView.as_view(pattern_name='home', permanent=True), name='logged_home'),
    path('products/products/', RedirectView.as_view(pattern_name='tienda:producto_list', permanent=False), name='legacy_products_products_i18n'),
    path('acerca-de/', views.acerca_de, name='acerca_de'),
    path('contacto/', views.contacto, name='contacto'),
    path('politicas-privacidad-usuario/', views.politicas_privacidad_usuario, name='politicas_privacidad_usuario'),
    path('politica-privacidad/', views.politica_privacidad, name='politica_privacidad'),
    path('terminos/', views.terminos, name='terminos'),
    path('politica-cambios/', views.politica_cambios, name='politica_cambios'),
    path('politica-devoluciones/', views.politica_devoluciones, name='politica_devoluciones'),
    path('politica-garantia/', views.politica_garantia, name='politica_garantia'),
    path('politica-tratamiento-datos/', views.politica_tratamiento_datos, name='politica_tratamiento_datos'),
    path('politica-cookies/', views.politica_cookies, name='politica_cookies'),
    path('politica-envios/', views.politica_envios, name='politica_envios'),
    path('politica-pagos/', views.politica_pagos, name='politica_pagos'),
    path(settings.ADMIN_URL, admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('afiliados/', include('afiliados.urls')),
    # Ruta anterior del programa (antes se llamaba "influencer"): se redirige
    # para no romper enlaces guardados o enviados por correo.
    path('influencer/', views.ruta_antigua_de_afiliados, {'resto': ''}),
    path('influencer/<path:resto>', views.ruta_antigua_de_afiliados),
    path('blog/', include('blog.urls', namespace='blog')),
    path('admin-panel/', include('administracion.urls')),
    path('contabilidad/', include('contabilidad.urls', namespace='contabilidad')),
    path('analitica/', include('analitica.urls', namespace='analitica')),
    path('tienda/', include('tienda.urls', namespace='tienda')),
    path('carrito/', include('carrito.urls', namespace='carrito')),
    path('pedidos-tienda/', include('orders.urls', namespace='orders')),
    path('pagos/', include('payments.urls', namespace='payments')),
)

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = 'gotogym.errores.error_400'
handler403 = 'gotogym.errores.error_403'
handler404 = 'gotogym.errores.error_404'
handler500 = 'gotogym.errores.error_500'
