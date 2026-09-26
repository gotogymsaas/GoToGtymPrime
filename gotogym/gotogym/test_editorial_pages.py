"""Contrato editorial compartido para Journal, marca, cuenta y pedidos."""
from decimal import Decimal

from blog.models import Category, Post
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant


class EditorialPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email='editorial@example.com', username='editorial', password='secret123',
            first_name='Eva', last_name='Editorial',
        )

    def test_about_despliega_historia_y_pilares_de_marca(self):
        response = self.client.get(reverse('acerca_de'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tecnología alrededor de')
        self.assertContains(response, 'Personalización')
        self.assertTemplateUsed(response, 'static_pages/about.html')

    def test_journal_sin_posts_no_muestra_filtros(self):
        response = self.client.get(reverse('blog:post_list'))

        self.assertContains(response, 'Estamos preparando historias para avanzar')
        self.assertNotContains(response, 'journal-search')

    def test_journal_con_posts_muestra_filtros_y_estado_sin_coincidencias(self):
        category = Category.objects.create(name='Diseño')
        Post.objects.create(
            title='Diseño que acompaña', category=category, author=self.user,
            excerpt='Una historia editorial.', content='Contenido.',
        )

        response = self.client.get(reverse('blog:post_list'), {'search': 'inexistente'})

        self.assertContains(response, 'journal-search')
        self.assertContains(response, 'No encontramos historias con esos filtros')

    def test_perfil_separa_datos_y_seguridad_y_vuelve_al_home_autenticado(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('edit_profile'))

        self.assertContains(response, 'Datos personales')
        self.assertContains(response, '<details class="account-security">', html=False)
        self.assertContains(response, reverse('logged_home'))

    def test_pedidos_vacios_reciben_recomendaciones_comprables(self):
        category = ProductCategory.objects.create(name='Editorial recommendation')
        brand = Brand.objects.create(name='Editorial brand')
        product = Product.objects.create(
            name='Motion Essential', category=category, brand=brand,
            base_price=Decimal('120000.0000'), featured=True,
        )
        variant = ProductVariant.objects.create(
            product=product, sku='EDITORIAL-M-BLK', size='M', color='negro',
        )
        Inventory.objects.create(variant=variant, quantity_available=3)
        self.client.force_login(self.user)

        response = self.client.get(reverse('orders:my_orders'))

        self.assertContains(response, 'Todavía no tienes pedidos')
        recommendations = response.context['recommended_cards']
        self.assertEqual(len(recommendations), 3)
        self.assertTrue(all(card['in_stock'] for card in recommendations))
        self.assertContains(response, '/static/product_media/')

    def test_entrada_publica_conserva_experiencia_quantum(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'class="figma-home"', html=False)
        self.assertContains(response, 'class="quantum-field"', html=False)

    def test_contacto_conserva_fondo_quantum_con_shell_editorial(self):
        response = self.client.get(reverse('contacto'))

        self.assertContains(response, 'editorial-quantum__background')
        self.assertContains(response, 'support@gotogym.store')
        self.assertContains(response, 'Privacidad y tratamiento de datos')

    def test_todas_las_politicas_comparten_shell_y_navegacion(self):
        routes = [
            'politica_privacidad', 'terminos', 'politica_cambios',
            'politica_devoluciones', 'politica_garantia', 'politica_envios',
            'politica_pagos', 'politica_tratamiento_datos',
        ]

        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'editorial-quantum__background')
                self.assertContains(response, 'Ayuda y transparencia')
                self.assertContains(response, reverse('contacto'))

    def test_politica_activa_se_identifica_en_navegacion(self):
        response = self.client.get(reverse('politica_envios'))

        self.assertContains(response, 'href="{}" aria-current="page"'.format(reverse('politica_envios')))
