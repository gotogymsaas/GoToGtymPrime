"""Favoritos: guardar y quitar desde la foto, y la lista en el perfil."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductFavorite, ProductVariant

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def _crear_producto(nombre, categoria, marca, activo=True):
    producto = Product.objects.create(
        name=nombre, category=categoria, brand=marca, base_price=Decimal('100000.0000'), stock=0,
    )
    variante = ProductVariant.objects.create(
        product=producto, sku=f'FAV-{nombre[:20]}', size='M', color='negro', is_active=activo,
    )
    Inventory.objects.create(variant=variante, quantity_available=5)
    return producto


def _crear_usuario(correo):
    return get_user_model().objects.create_user(email=correo, username=correo, password='secret123')


class FavoritosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria favoritos')
        marca = Brand.objects.create(name='Marca favoritos')
        cls.camiseta = _crear_producto('Camiseta favorita', categoria, marca)
        cls.legging = _crear_producto('Legging favorito', categoria, marca)
        cls.retirado = _crear_producto('Producto retirado', categoria, marca, activo=False)
        cls.usuario = _crear_usuario('favoritos@example.com')
        cls.otro = _crear_usuario('otro-favoritos@example.com')

    def _url(self, producto):
        return reverse('tienda:favorito', args=[producto.pk])

    # --- Endpoint ---------------------------------------------------------

    def test_agregar_y_quitar_con_javascript(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.post(self._url(self.camiseta), {'favorito': '1'}, **AJAX)
        self.assertEqual(respuesta.json(), {'ok': True, 'favorito': True})
        self.assertTrue(ProductFavorite.objects.filter(user=self.usuario, product=self.camiseta).exists())

        respuesta = self.client.post(self._url(self.camiseta), {'favorito': '0'}, **AJAX)
        self.assertEqual(respuesta.json(), {'ok': True, 'favorito': False})
        self.assertFalse(ProductFavorite.objects.filter(user=self.usuario).exists())

    def test_es_idempotente_ante_doble_clic(self):
        """El formulario envia el estado deseado: dos "agregar" seguidos no
        lo dejan fuera ni duplican la fila."""
        self.client.force_login(self.usuario)
        self.client.post(self._url(self.camiseta), {'favorito': '1'}, **AJAX)
        respuesta = self.client.post(self._url(self.camiseta), {'favorito': '1'}, **AJAX)

        self.assertTrue(respuesta.json()['favorito'])
        self.assertEqual(ProductFavorite.objects.filter(user=self.usuario, product=self.camiseta).count(), 1)

    def test_sin_javascript_vuelve_a_la_pagina_de_origen(self):
        self.client.force_login(self.usuario)
        origen = reverse('tienda:producto_list') + '?talla=M&page=2'

        respuesta = self.client.post(self._url(self.camiseta), {'favorito': '1', 'next': origen})

        self.assertRedirects(respuesta, origen, fetch_redirect_response=False)
        self.assertTrue(ProductFavorite.objects.filter(user=self.usuario, product=self.camiseta).exists())

    def test_no_redirige_a_otro_sitio(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.post(self._url(self.camiseta), {'favorito': '1', 'next': 'https://malicioso.example/'})

        self.assertRedirects(
            respuesta, reverse('tienda:producto_detail', args=[self.camiseta.pk]), fetch_redirect_response=False,
        )

    def test_sin_sesion_pide_iniciar_sesion_y_no_guarda(self):
        origen = reverse('tienda:producto_detail', args=[self.camiseta.pk])

        respuesta = self.client.post(self._url(self.camiseta), {'favorito': '1', 'next': origen}, **AJAX)

        self.assertEqual(respuesta.status_code, 401)
        login_url = respuesta.json()['login_url']
        self.assertTrue(login_url.startswith(resolve_url(settings.LOGIN_URL)))
        self.assertIn('next=', login_url)
        self.assertFalse(ProductFavorite.objects.exists())

    def test_sin_sesion_y_sin_javascript_redirige_al_login(self):
        respuesta = self.client.post(self._url(self.camiseta), {'favorito': '1'})

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta['Location'].startswith(resolve_url(settings.LOGIN_URL)))
        self.assertFalse(ProductFavorite.objects.exists())

    def test_solo_acepta_post(self):
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(self._url(self.camiseta)).status_code, 405)

    def test_un_producto_fuera_del_catalogo_no_se_puede_guardar(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.post(self._url(self.retirado), {'favorito': '1'}, **AJAX)

        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(ProductFavorite.objects.exists())

    # --- Corazon en la tienda ---------------------------------------------

    def _estado_del_corazon(self, html, producto):
        """aria-pressed del corazon de ese producto en la pagina."""
        inicio = html.index(f'action="{self._url(producto)}"')
        fragmento = html[inicio:html.index('</form>', inicio)]
        return fragmento.split('aria-pressed="', 1)[1].split('"', 1)[0]

    def test_el_grid_pinta_el_corazon_segun_el_estado(self):
        ProductFavorite.objects.create(user=self.usuario, product=self.camiseta)
        self.client.force_login(self.usuario)

        # El filtro deja solo los productos de la prueba en la primera pagina,
        # aunque la base traiga el catalogo sembrado por las migraciones.
        respuesta = self.client.get(reverse('tienda:producto_list'), {'filtro': 'favorit'})

        self.assertEqual(respuesta.context['favoritos_ids'], frozenset({self.camiseta.pk}))
        html = respuesta.content.decode()
        self.assertIn(self._url(self.legging), html)
        self.assertEqual(self._estado_del_corazon(html, self.camiseta), 'true')
        self.assertEqual(self._estado_del_corazon(html, self.legging), 'false')
        # Solo el favorito sale lleno; el resto del catalogo, vacio.
        self.assertEqual(html.count('data-favorito-tooltip="Quitar de favoritos"'), 1)

    def test_el_grid_muestra_el_corazon_sin_sesion(self):
        # El filtro deja solo los productos de la prueba en la primera pagina,
        # aunque la base traiga el catalogo sembrado por las migraciones.
        respuesta = self.client.get(reverse('tienda:producto_list'), {'filtro': 'favorit'})

        self.assertEqual(respuesta.context['favoritos_ids'], frozenset())
        html = respuesta.content.decode()
        self.assertEqual(self._estado_del_corazon(html, self.camiseta), 'false')
        self.assertNotIn('data-favorito-tooltip="Quitar de favoritos"', html)

    def test_la_ficha_pinta_el_corazon_en_la_galeria(self):
        ProductFavorite.objects.create(user=self.usuario, product=self.camiseta)
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse('tienda:producto_detail', args=[self.camiseta.pk]))

        self.assertContains(respuesta, 'gtg-favorito--galeria')
        self.assertContains(respuesta, 'aria-pressed="true"')

    # --- Pagina de favoritos ----------------------------------------------

    def test_la_pagina_pide_iniciar_sesion(self):
        respuesta = self.client.get(reverse('tienda:favoritos'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta['Location'].startswith(resolve_url(settings.LOGIN_URL)))

    def test_lista_los_favoritos_del_mas_reciente_al_mas_antiguo(self):
        antiguo = ProductFavorite.objects.create(user=self.usuario, product=self.camiseta)
        ProductFavorite.objects.filter(pk=antiguo.pk).update(created_at=timezone.now() - timedelta(days=3))
        ProductFavorite.objects.create(user=self.usuario, product=self.legging)
        # El favorito de otra persona sobre el mismo producto no altera la
        # lista ni el orden.
        ProductFavorite.objects.create(user=self.otro, product=self.camiseta)
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse('tienda:favoritos'))

        productos = [card['product'] for card in respuesta.context['favoritos_cards']]
        self.assertEqual(productos, [self.legging, self.camiseta])
        self.assertContains(respuesta, 'data-favoritos-lista')

    def test_oculta_productos_que_salieron_del_catalogo(self):
        ProductFavorite.objects.create(user=self.usuario, product=self.retirado)
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse('tienda:favoritos'))

        self.assertEqual(respuesta.context['favoritos_cards'], [])
        self.assertContains(respuesta, 'Todavía no tienes favoritos')

    def test_recomienda_de_las_mismas_categorias_sin_repetir_ni_agotados(self):
        marca = self.camiseta.brand
        otra_categoria = ProductCategory.objects.create(name='Otra categoria favoritos')
        de_otra_categoria = _crear_producto('Producto de otra categoria', otra_categoria, marca)
        agotado = _crear_producto('Relacionado agotado', self.camiseta.category, marca)
        Inventory.objects.filter(variant__product=agotado).update(quantity_available=0)
        ProductFavorite.objects.create(user=self.usuario, product=self.camiseta)
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse('tienda:favoritos'))

        relacionados = [card['product'] for card in respuesta.context['relacionados_cards']]
        self.assertEqual(relacionados, [self.legging])
        self.assertNotIn(de_otra_categoria, relacionados)
        self.assertContains(respuesta, 'data-carrusel-pista')
        self.assertContains(respuesta, 'Relacionados con tus favoritos')

    def test_sin_favoritos_recomienda_la_seleccion_de_la_tienda(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse('tienda:favoritos'))

        self.assertTrue(respuesta.context['relacionados_cards'])
        self.assertContains(respuesta, 'Un buen lugar para empezar.')

    def test_el_menu_lleva_a_la_pagina_de_favoritos(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse('tienda:producto_list'))

        self.assertContains(respuesta, f'href="{reverse("tienda:favoritos")}"', count=2)

    def test_el_perfil_ya_no_lista_favoritos(self):
        ProductFavorite.objects.create(user=self.usuario, product=self.camiseta)
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse('edit_profile'))

        self.assertNotIn('favoritos_cards', respuesta.context)
        self.assertNotContains(respuesta, 'data-favoritos-lista')
