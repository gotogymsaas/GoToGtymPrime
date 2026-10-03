"""SEO: robots.txt, sitemap.xml, metadatos y datos estructurados."""
import json
import re
from decimal import Decimal

from blog.models import Post
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

from .seo import contexto_seo, json_ld, recortar


def _json_ld(html):
    """Todos los objetos JSON-LD de la pagina (un bloque puede traer una lista)."""
    objetos = []
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        dato = json.loads(bloque)
        objetos.extend(dato if isinstance(dato, list) else [dato])
    return objetos


def _meta(html, nombre, atributo='name'):
    m = re.search(rf'<meta {atributo}="{re.escape(nombre)}" content="([^"]*)"', html)
    return m.group(1) if m else None


class UtilidadesTests(SimpleTestCase):
    def test_recortar_corta_en_palabra_completa_y_une_espacios(self):
        texto = 'Una   prenda\ncon   tecnología ' + 'larga ' * 60
        resumen = recortar(texto, 60)
        self.assertLessEqual(len(resumen), 60)
        self.assertTrue(resumen.endswith('…'))
        self.assertNotIn('  ', resumen)
        self.assertNotIn('\n', resumen)

    def test_recortar_deja_intacto_un_texto_corto(self):
        self.assertEqual(recortar('Hola mundo'), 'Hola mundo')
        self.assertEqual(recortar(None), '')

    def test_json_ld_escapa_lo_que_podria_cerrar_la_etiqueta(self):
        salida = json_ld({'name': '</script><script>alert(1)</script> & <b>'})
        self.assertNotIn('<', salida)
        self.assertNotIn('>', salida)
        self.assertEqual(json.loads(salida)['name'], '</script><script>alert(1)</script> & <b>')

    def test_contexto_seo_incluye_solo_lo_que_se_entrega(self):
        self.assertNotIn('seo_json_ld', contexto_seo('T', 'D'))
        self.assertNotIn('seo_image', contexto_seo('T', 'D'))
        completo = contexto_seo('T', 'D', tipo='product', imagen='https://x/y.png', datos={'a': 1})
        self.assertEqual(completo['seo_type'], 'product')
        self.assertEqual(completo['seo_image'], 'https://x/y.png')
        self.assertIn('"a": 1', completo['seo_json_ld'])


class RobotsYSitemapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria seo')
        marca = Brand.objects.create(name='Marca seo')
        cls.producto = Product.objects.create(
            name='Producto seo', category=categoria, brand=marca, base_price=Decimal('90000'), stock=0,
        )
        autor = get_user_model().objects.create_user(email='seo@example.com', username='seo', password='x')
        cls.publicada = Post.objects.create(title='Entrada publica', author=autor, content='x', is_published=True)
        cls.borrador = Post.objects.create(title='Entrada borrador', author=autor, content='x', is_published=False)

    def test_robots_bloquea_lo_privado_en_todos_los_idiomas_e_indica_el_sitemap(self):
        respuesta = self.client.get('/robots.txt')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('text/plain', respuesta['Content-Type'])
        texto = respuesta.content.decode()
        self.assertIn('Disallow: /es/admin-panel/', texto)
        self.assertIn('Disallow: /en/carrito/', texto)
        self.assertIn('Disallow: /pt/pedidos-tienda/', texto)
        self.assertIn('Disallow: /api/', texto)
        self.assertIn('Sitemap: http://testserver/sitemap.xml', texto)
        self.assertNotIn('Disallow: /es/tienda/', texto)

    def test_sitemap_lista_paginas_productos_y_entradas_publicadas(self):
        respuesta = self.client.get('/sitemap.xml')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('xml', respuesta['Content-Type'])
        xml = respuesta.content.decode()
        for ruta in ('/es/', '/es/tienda/', '/es/blog/', '/es/acerca-de/', '/es/contacto/'):
            self.assertIn(f'http://testserver{ruta}</loc>', xml, ruta)
        self.assertIn(f'/es/tienda/producto/{self.producto.pk}/</loc>', xml)
        self.assertIn(f'/es/blog/{self.publicada.slug}/</loc>', xml)

    def test_sitemap_excluye_borradores_privado_politicas_y_otros_idiomas(self):
        xml = self.client.get('/sitemap.xml').content.decode()
        self.assertNotIn(self.borrador.slug, xml)
        for excluido in ('/carrito/', '/pedidos-tienda/', '/accounts/', '/admin-panel/', '/politica-', '/terminos/'):
            self.assertNotIn(excluido, xml, excluido)
        self.assertNotIn('/en/', xml)
        self.assertNotIn('/pt/', xml)


class MetadatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria meta')
        marca = Brand.objects.create(name='Marca meta')
        cls.producto = Product.objects.create(
            name='Chaqueta </script>', category=categoria, brand=marca, base_price=Decimal('100000'), stock=0,
            description='Chaqueta ligera. ' + 'Muy cómoda. ' * 40,
        )
        cls.v1 = ProductVariant.objects.create(product=cls.producto, sku='META-S', size='S', color='negro')
        cls.v2 = ProductVariant.objects.create(
            product=cls.producto, sku='META-M', size='M', color='negro', price_override=Decimal('130000'),
        )
        Inventory.objects.create(variant=cls.v1, quantity_available=3)
        Inventory.objects.create(variant=cls.v2, quantity_available=3)
        autor = get_user_model().objects.create_user(
            email='meta@example.com', username='meta', password='x', first_name='Ana', last_name='Soto',
        )
        cls.post = Post.objects.create(
            title='Un articulo', author=autor, excerpt='Resumen del articulo.', content='Cuerpo.', is_published=True,
        )

    def _html(self, url, **extra):
        return self.client.get(url, **extra).content.decode()

    def test_portada_con_descripcion_open_graph_canonica_y_datos_de_organizacion(self):
        html = self._html(reverse('home'))
        self.assertIn('Ropa deportiva con tecnología textil', _meta(html, 'description'))
        self.assertEqual(_meta(html, 'og:title', 'property'), 'GoToGym: diseñada para tu forma de avanzar')
        self.assertEqual(_meta(html, 'og:type', 'property'), 'website')
        self.assertEqual(_meta(html, 'twitter:card'), 'summary_large_image')
        self.assertIn('hero_gotogym', _meta(html, 'og:image', 'property'))
        self.assertIn('<link rel="canonical" href="http://testserver/es/">', html)
        tipos = {d['@type'] for d in _json_ld(html)}
        self.assertEqual(tipos, {'Organization', 'WebSite'})

    def test_la_canonica_no_incluye_filtros_ni_paginacion(self):
        html = self._html(reverse('tienda:producto_list') + '?filtro=chaqueta&page=2')
        self.assertIn('<link rel="canonical" href="http://testserver/es/tienda/">', html)

    def test_ficha_de_producto_con_datos_estructurados(self):
        html = self._html(reverse('tienda:producto_detail', args=[self.producto.pk]))
        self.assertEqual(_meta(html, 'og:type', 'property'), 'product')
        self.assertLessEqual(len(_meta(html, 'description')), 156)
        producto = _json_ld(html)[0]
        self.assertEqual(producto['@type'], 'Product')
        self.assertEqual(producto['brand']['name'], 'Marca meta')
        self.assertEqual(producto['category'], 'Categoria meta')
        oferta = producto['offers']
        self.assertEqual(oferta['@type'], 'AggregateOffer')  # precios distintos entre variantes
        self.assertEqual((oferta['lowPrice'], oferta['highPrice'], oferta['offerCount']), ('100000', '130000', 2))
        self.assertEqual(oferta['priceCurrency'], 'COP')
        self.assertEqual(oferta['availability'], 'https://schema.org/InStock')

    def test_un_nombre_con_script_no_puede_romper_la_etiqueta(self):
        html = self._html(reverse('tienda:producto_detail', args=[self.producto.pk]))
        self.assertEqual(len(re.findall(r'<script type="application/ld\+json">', html)), 1)
        self.assertEqual(_json_ld(html)[0]['name'], 'Chaqueta </script>')
        self.assertNotIn('Chaqueta </script>"', html)

    def test_producto_de_un_solo_precio_usa_oferta_simple(self):
        ProductVariant.objects.filter(pk=self.v2.pk).update(price_override=None)
        oferta = _json_ld(self._html(reverse('tienda:producto_detail', args=[self.producto.pk])))[0]['offers']
        self.assertEqual(oferta['@type'], 'Offer')
        self.assertEqual(oferta['price'], '100000')

    def test_sin_stock_el_producto_figura_agotado(self):
        Inventory.objects.update(quantity_available=0)
        oferta = _json_ld(self._html(reverse('tienda:producto_detail', args=[self.producto.pk])))[0]['offers']
        self.assertEqual(oferta['availability'], 'https://schema.org/OutOfStock')

    def test_entrada_del_journal_como_articulo(self):
        html = self._html(reverse('blog:post_detail', args=[self.post.slug]))
        self.assertEqual(_meta(html, 'og:type', 'property'), 'article')
        self.assertEqual(_meta(html, 'description'), 'Resumen del articulo.')
        articulo = _json_ld(html)[0]
        self.assertEqual(articulo['@type'], 'Article')
        self.assertEqual(articulo['headline'], 'Un articulo')
        self.assertEqual(articulo['author']['name'], 'Ana Soto')

    def test_acerca_de_contacto_y_journal_tienen_su_propia_descripcion(self):
        descripciones = {
            _meta(self._html(reverse(nombre)), 'description')
            for nombre in ('acerca_de', 'contacto', 'blog:post_list', 'tienda:producto_list', 'home')
        }
        self.assertEqual(len(descripciones), 5)
        self.assertNotIn(None, descripciones)


class PaginasPrivadasTests(TestCase):
    def test_lo_privado_lleva_noindex_y_lo_publico_no(self):
        for nombre in ('carrito:cart_detail', 'commercial_login', 'register', 'password_reset_form'):
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertIn('<meta name="robots" content="noindex, nofollow">', html, nombre)
        for nombre in ('home', 'tienda:producto_list', 'blog:post_list', 'acerca_de', 'contacto'):
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertNotIn('name="robots"', html, nombre)

    def test_el_panel_administrativo_lleva_noindex(self):
        staff = get_user_model().objects.create_user(email='s@example.com', username='s', password='x', is_staff=True)
        self.client.force_login(staff)
        html = self.client.get(reverse('admin_dashboard')).content.decode()
        self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
