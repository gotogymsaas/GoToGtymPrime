"""Mapa del sitio para buscadores.

Solo lo que tiene sentido indexar: portada, tienda, Journal, Acerca de,
Contacto, cada producto y cada entrada publicada.

Quedan fuera, a proposito:
- las paginas de politicas, mientras su texto sea provisional;
- todo lo privado (carrito, checkout, cuenta, paneles), que tambien se
  excluye en `robots.txt` y con `noindex`;
- los idiomas ingles y portugues: gran parte del contenido sigue solo en
  espanol y publicarlo en tres idiomas duplicaria paginas casi identicas.
"""
from blog.models import Post
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from products.models import Product


class PaginasPublicas(Sitemap):
    i18n = True
    languages = ['es']
    changefreq = 'weekly'

    _PRIORIDADES = {'home': 1.0, 'tienda:producto_list': 0.9, 'blog:post_list': 0.7}

    def items(self):
        return ['home', 'tienda:producto_list', 'blog:post_list', 'acerca_de', 'contacto']

    def location(self, item):
        return reverse(item)

    def priority(self, item):  # type: ignore[override]
        return self._PRIORIDADES.get(item, 0.5)


class Productos(Sitemap):
    i18n = True
    languages = ['es']
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Product.objects.order_by('pk')

    def location(self, item):
        return reverse('tienda:producto_detail', args=[item.pk])


class EntradasDelJournal(Sitemap):
    i18n = True
    languages = ['es']
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Post.objects.filter(is_published=True).order_by('-published')

    def location(self, item):
        return reverse('blog:post_detail', args=[item.slug])

    def lastmod(self, item):
        return item.updated


SITEMAPS = {
    'paginas': PaginasPublicas,
    'productos': Productos,
    'journal': EntradasDelJournal,
}
