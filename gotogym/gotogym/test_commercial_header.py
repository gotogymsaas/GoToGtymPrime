"""Contrato del header comercial compartido por todo el sitio autenticado.

La barra dejo de ser una portada con hamburguesa en todos los anchos: la
tienda, el Journal y la busqueda viven en la propia barra, y anadir al
carrito ya no obliga a abandonar el catalogo. Estas pruebas fijan lo que
no debe volver atras.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant


class CommercialHeaderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email='header@example.com', username='header', password='secret123',
            first_name='Hana',
        )
        category = ProductCategory.objects.create(name='Header category')
        brand = Brand.objects.create(name='Header brand')
        cls.product = Product.objects.create(
            name='Header Motion Short', category=category, brand=brand,
            base_price=Decimal('75000.0000'), featured=True,
        )
        cls.variant = ProductVariant.objects.create(
            product=cls.product, sku='HEAD-M-BLK', size='M', color='negro',
        )
        Inventory.objects.create(variant=cls.variant, quantity_available=6)

    def _html(self, url):
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, url)
        return respuesta.content.decode()

    def _navegacion(self, html):
        """Devuelve solo el fragmento de la navegacion persistente."""
        self.assertIn('class="gtg-nav-links"', html)
        inicio = html.index('class="gtg-nav-links"')
        return html[inicio:html.index('</ul>', inicio)]

    def test_la_tienda_esta_en_la_barra_y_no_solo_en_el_panel_movil(self):
        self.client.force_login(self.user)

        for url in [reverse('logged_home'), reverse('tienda:producto_list'),
                    reverse('carrito:cart_detail')]:
            with self.subTest(url=url):
                navegacion = self._navegacion(self._html(url))
                self.assertIn(reverse('tienda:producto_list'), navegacion)
                self.assertIn(reverse('blog:post_list'), navegacion)
                self.assertIn(reverse('contacto'), navegacion)

    def test_la_pagina_actual_se_marca_en_la_navegacion(self):
        self.client.force_login(self.user)

        navegacion = self._navegacion(self._html(reverse('tienda:producto_list')))

        self.assertIn('aria-current="page"', navegacion)

    def test_el_buscador_apunta_a_la_tienda_con_el_parametro_de_la_plp(self):
        self.client.force_login(self.user)
        html = self._html(reverse('logged_home'))

        self.assertIn('class="gtg-nav-search"', html)
        url_tienda = reverse('tienda:producto_list')
        self.assertIn(f'action="{url_tienda}"', html)
        self.assertIn('name="filtro"', html)

    def test_el_buscador_de_la_barra_filtra_de_verdad(self):
        self.client.force_login(self.user)

        respuesta = self.client.get(reverse('tienda:producto_list'),
                                    {'filtro': 'Header Motion'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Header Motion Short')

    def test_la_ficha_declara_el_formulario_que_intercepta_el_header(self):
        self.client.force_login(self.user)

        html = self._html(reverse('tienda:producto_detail', args=[self.product.pk]))

        self.assertIn('data-add-to-cart', html)
        self.assertIn('data-product-name="Header Motion Short"', html)
        self.assertIn('data-minicart', html)

    def test_agregar_al_carrito_por_ajax_no_saca_del_catalogo(self):
        self.client.force_login(self.user)

        respuesta = self.client.post(
            reverse('carrito:add_to_cart', args=[self.variant.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        # Sin redireccion: el comprador se queda en la ficha y el panel del
        # header muestra esta respuesta.
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {'success': True, 'cart_count': 1})

    def test_el_salto_al_contenido_es_el_primer_enlace_de_la_pagina(self):
        self.client.force_login(self.user)

        html = self._html(reverse('logged_home'))

        self.assertIn('class="gtg-skip-link" href="#main-content"', html)
        self.assertLess(html.index('gtg-skip-link'), html.index('gtg-navbar'))

    def test_el_comportamiento_del_header_viaja_en_un_archivo_cacheable(self):
        self.client.force_login(self.user)

        html = self._html(reverse('logged_home'))

        self.assertIn('js/commerce_header.js', html)
        # El panel movil y el menu de cuenta se ocultan con el atributo
        # nativo, no con la clase .hidden que servia Tailwind por CDN.
        self.assertNotIn('onclick="toggleMobileMenu', html)
        self.assertNotIn('onclick="toggleUserMenu', html)

    def test_quien_no_es_influencer_ve_el_enlace_para_serlo(self):
        # Reemplaza al modal que vivia en home.html (retirado en 04c678d):
        # esa vista redirige a los usuarios con sesion antes de que el
        # modal pudiera mostrarse, asi que habia quedado inalcanzable. Vive
        # aqui y no en el Home porque el programa de influencers debe
        # quedar fuera del camino critico de compra (ver
        # PROPUESTA_HOME_STORE_QUANTUM.md, seccion 2).
        self.client.force_login(self.user)

        html = self._html(reverse('logged_home'))

        self.assertIn(reverse('influencer_suscribete'), html)
        self.assertIn('Hazte influencer', html)
        self.assertNotIn('Panel influencer', html)

    def test_quien_ya_es_influencer_ve_su_panel_y_no_la_invitacion(self):
        from influencer.models import InfluencerProfile

        InfluencerProfile.objects.create(user=self.user)
        self.client.force_login(self.user)

        html = self._html(reverse('logged_home'))

        self.assertIn(reverse('influencer_dashboard'), html)
        self.assertIn('Panel influencer', html)
        self.assertNotIn('Hazte influencer', html)
