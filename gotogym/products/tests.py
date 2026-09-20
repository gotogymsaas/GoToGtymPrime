"""CRUD heredado de products: control de acceso y deprecacion.

Estas vistas ya no hacen nada por si mismas: redirigen al panel
`administracion` (las de HTML) o devuelven 410 sin mutar nada (las dos de
AJAX). Estos tests verifican that (a) siguen exigiendo `is_staff`, y (b)
ninguna de ellas ejecuta ya ninguna mutacion real sobre el catalogo.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Brand, Product, ProductCategory


class ProductsCrudAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff_user = User.objects.create_user(
            email='staff@example.com',
            username='staff@example.com',
            password='secret123',
            is_staff=True,
        )
        cls.regular_user = User.objects.create_user(
            email='cliente@example.com',
            username='cliente@example.com',
            password='secret123',
        )
        # Nombres deliberadamente distintos a los del catalogo semilla
        # (migraciones 0004-0006 de products), que ya crean categorias y
        # marcas reales y colisionarian por el `unique=True` del campo name.
        cls.category = ProductCategory.objects.create(name='Categoria de prueba')
        cls.brand = Brand.objects.create(name='Marca de prueba')
        cls.product = Product.objects.create(
            name='Legging de prueba',
            category=cls.category,
            brand=cls.brand,
            base_price='100000.0000',
            stock=5,
        )

    def _protected_get_urls(self):
        return [
            reverse('products:add_category'),
            reverse('products:add_product'),
            reverse('products:list_category'),
            reverse('products:list_product'),
            reverse('products:view_product', args=[self.product.pk]),
            reverse('products:edit_product', args=[self.product.pk]),
            reverse('products:delete_product', args=[self.product.pk]),
            reverse('products:edit_category', args=[self.category.pk]),
            reverse('products:delete_category', args=[self.category.pk]),
            reverse('products:view_category', args=[self.category.pk]),
            reverse('products:brand_list'),
            reverse('products:brand_edit', args=[self.brand.pk]),
            reverse('products:brand_preview', args=[self.brand.pk]),
        ]

    def test_anonymous_user_is_redirected_to_login(self):
        for url in self._protected_get_urls():
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 302,
                f'{url} deberia redirigir (302) a login para un usuario anonimo',
            )
            self.assertIn('acceso', response.url)

    def test_non_staff_user_is_redirected_to_login(self):
        self.client.force_login(self.regular_user)
        for url in self._protected_get_urls():
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 302,
                f'{url} deberia redirigir (302) para un usuario autenticado sin is_staff',
            )
            self.assertIn('acceso', response.url)

    def test_staff_user_is_redirected_to_the_admin_panel_not_rendered(self):
        """El CRUD esta deprecado: un staff que llega aqui se redirige al
        panel autoritativo en vez de ver el formulario viejo."""
        self.client.force_login(self.staff_user)
        for url in self._protected_get_urls():
            response = self.client.get(url, follow=False)
            self.assertEqual(
                response.status_code, 302,
                f'{url} deberia redirigir (302) al panel de administracion',
            )
            self.assertNotIn('acceso', response.url, f'{url} no deberia mandar a login para un staff')

    def test_ajax_endpoints_return_410_and_do_not_mutate(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse('products:delete_product_image', args=[self.product.pk]))
        self.assertEqual(response.status_code, 410)

        response = self.client.post(reverse('products:delete_category_ajax', args=[self.category.pk]))
        self.assertEqual(response.status_code, 410)

        self.assertTrue(ProductCategory.objects.filter(pk=self.category.pk).exists())

    def test_anonymous_post_mutations_are_blocked_and_nothing_changes(self):
        mutation_urls = [
            reverse('products:delete_product_image', args=[self.product.pk]),
            reverse('products:delete_category_ajax', args=[self.category.pk]),
            reverse('products:brand_delete', args=[self.brand.pk]),
            reverse('products:delete_product', args=[self.product.pk]),
            reverse('products:delete_category', args=[self.category.pk]),
        ]
        for url in mutation_urls:
            response = self.client.post(url, {})
            self.assertEqual(
                response.status_code, 302,
                f'{url} deberia redirigir (302) a login en vez de ejecutar la mutacion',
            )

        # Nada debe haberse borrado ni mutado pese a los POST anonimos.
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertTrue(Brand.objects.filter(pk=self.brand.pk).exists())
        self.assertTrue(ProductCategory.objects.filter(pk=self.category.pk).exists())

    def test_staff_post_mutations_no_longer_delete_anything(self):
        """Aunque un staff intente usar estas URLs viejas para borrar, ya
        no ejecutan la mutacion: redirigen o devuelven 410."""
        self.client.force_login(self.staff_user)

        self.client.post(reverse('products:delete_product', args=[self.product.pk]))
        self.client.post(reverse('products:delete_category', args=[self.category.pk]))
        self.client.post(reverse('products:brand_delete', args=[self.brand.pk]))

        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertTrue(ProductCategory.objects.filter(pk=self.category.pk).exists())
        self.assertTrue(Brand.objects.filter(pk=self.brand.pk).exists())

    def test_el_catalogo_exige_sesion_pero_no_ser_staff(self):
        """Store requiere sesion iniciada; un cliente sin `is_staff` debe
        poder verlo, a diferencia del CRUD de administracion."""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse('tienda:producto_list'))
        self.assertEqual(response.status_code, 200)
