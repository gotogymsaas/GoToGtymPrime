"""Cobertura del Home comercial autenticado."""
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blog.models import Category, Post
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant


class LoggedHomeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Las migraciones incluyen un catalogo demostrativo. El caso de prueba
        # usa un conjunto controlado para comprobar orden y limite con certeza.
        Product.objects.all().delete()
        cls.user = get_user_model().objects.create_user(
            email='home@example.com', username='home', password='secret123', first_name='Ana',
        )
        product_category = ProductCategory.objects.create(name='Performance')
        brand = Brand.objects.create(name='Marca Home Test')
        for index in range(5):
            product = Product.objects.create(
                name=f'Producto Home {index}',
                category=product_category,
                brand=brand,
                base_price=Decimal('150000.0000'),
                featured=index in (1, 3),
            )
            variant = ProductVariant.objects.create(
                product=product, sku=f'HOME-{index}-M', size='M', color='negro',
            )
            Inventory.objects.create(variant=variant, quantity_available=4)

        sold_out = Product.objects.create(
            name='Destacado sin disponibilidad',
            category=product_category,
            brand=brand,
            base_price=Decimal('190000.0000'),
            featured=True,
        )
        sold_out_variant = ProductVariant.objects.create(
            product=sold_out, sku='HOME-SOLD-OUT', size='S', color='gris',
        )
        Inventory.objects.create(variant=sold_out_variant, quantity_available=0)

        post_category = Category.objects.create(name='Tecnología')
        cls.post = Post.objects.create(
            title='Diseñar para el movimiento',
            author=cls.user,
            category=post_category,
            excerpt='Una mirada al diseño funcional de GoToGym.',
            content='Contenido editorial.',
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_home_renderiza_experiencia_comercial_y_journal(self):
        response = self.client.get(reverse('logged_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Diseñada para tu')
        self.assertContains(response, 'Hola, Ana')
        self.assertContains(response, 'Imagenes%20Home/bienestar_empresarial_5.jpeg')
        self.assertContains(response, 'Imagenes%20Home/WhatsApp%20Image%202026-07-21')
        self.assertContains(response, 'Campo', count=0)
        self.assertContains(response, self.post.title)
        self.assertContains(response, 'GoToGym Technology')
        self.assertNotContains(response, 'Vincularse como')

    def test_home_limita_productos_y_prioriza_destacados(self):
        response = self.client.get(reverse('logged_home'))
        cards = response.context['featured_cards']

        self.assertEqual(len(cards), 4)
        self.assertTrue(cards[0]['product'].featured)
        self.assertTrue(cards[1]['product'].featured)
        self.assertTrue(cards[0]['in_stock'])
        self.assertNotIn('Destacado sin disponibilidad', [card['product'].name for card in cards])

    def test_home_sin_contenido_renderiza_fallbacks_editoriales(self):
        Product.objects.all().delete()
        Post.objects.all().delete()

        response = self.client.get(reverse('logged_home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estamos preparando una selección extraordinaria')
        self.assertContains(response, 'Estamos preparando historias para avanzar')

    def test_home_exige_autenticacion(self):
        self.client.logout()

        response = self.client.get(reverse('logged_home'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('commercial_login'), response.url)

    def test_imagenes_editoriales_reutilizan_archivos_media_existentes(self):
        image_names = [
            'bienestar_empresarial_5.jpeg',
            'WhatsApp Image 2026-07-21 at 6.53.20 PM (2).jpeg',
            'WhatsApp Image 2026-07-21 at 6.53.19 PM (8).jpeg',
            'bienestar_empresarial_3.jpeg',
            'WhatsApp Image 2026-07-21 at 6.53.19 PM (1).jpeg',
        ]

        media_directory = Path(__file__).resolve().parents[1] / 'media' / 'products' / 'Imagenes Home'
        for image_name in image_names:
            with self.subTest(image=image_name):
                self.assertTrue((media_directory / image_name).is_file())
