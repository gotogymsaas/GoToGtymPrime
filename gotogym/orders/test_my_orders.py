"""Cuenta del cliente: historial de pedidos propio, nunca ajeno."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

from .services import create_order_from_cart

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class MyOrdersTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria mis pedidos')
        marca = Brand.objects.create(name='Marca mis pedidos')
        producto = Product.objects.create(
            name='Producto mis pedidos', category=categoria, brand=marca,
            base_price=Decimal('90000.0000'), stock=0,
        )
        cls.variante = _crear_variante(producto, 'MYO-001-S-NEG', 'S', 'negro', 10)

        User = get_user_model()
        cls.usuario_a = User.objects.create_user(
            email='usuario-a@example.com', username='usuario-a@example.com', password='secret123',
        )
        cls.usuario_b = User.objects.create_user(
            email='usuario-b@example.com', username='usuario-b@example.com', password='secret123',
        )

        cls.pedido_a1 = create_order_from_cart(cls.usuario_a, {str(cls.variante.pk): 1}, DATOS)
        cls.pedido_a2 = create_order_from_cart(cls.usuario_a, {str(cls.variante.pk): 1}, DATOS)
        cls.pedido_b1 = create_order_from_cart(cls.usuario_b, {str(cls.variante.pk): 1}, DATOS)

    def test_exige_sesion_iniciada(self):
        response = self.client.get(reverse('orders:my_orders'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)

    def test_lista_solo_los_pedidos_propios(self):
        self.client.force_login(self.usuario_a)
        response = self.client.get(reverse('orders:my_orders'))
        numeros = {order.order_number for order in response.context['orders']}
        self.assertEqual(numeros, {self.pedido_a1.order_number, self.pedido_a2.order_number})
        self.assertNotIn(self.pedido_b1.order_number, numeros)

    def test_no_muestra_pedidos_de_otro_usuario_en_el_html(self):
        self.client.force_login(self.usuario_a)
        response = self.client.get(reverse('orders:my_orders'))
        self.assertContains(response, self.pedido_a1.order_number)
        self.assertNotContains(response, self.pedido_b1.order_number)

    def test_usuario_sin_pedidos_ve_mensaje_vacio(self):
        User = get_user_model()
        nuevo = User.objects.create_user(
            email='sin-pedidos@example.com', username='sin-pedidos@example.com', password='secret123',
        )
        self.client.force_login(nuevo)
        response = self.client.get(reverse('orders:my_orders'))
        self.assertContains(response, 'Todavía no tienes pedidos')

    def test_acceso_directo_a_pedido_ajeno_por_numero_da_404_no_403(self):
        """Repetido explicitamente contra intento de acceso directo por
        order_number ajeno: debe dar 404 (sin filtrar si el pedido existe),
        nunca 403."""
        self.client.force_login(self.usuario_a)
        response = self.client.get(reverse('orders:order_detail', args=[self.pedido_b1.order_number]))
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(response.status_code, 403)

    def test_click_desde_mi_historial_si_lleva_al_propio_pedido(self):
        self.client.force_login(self.usuario_a)
        response = self.client.get(reverse('orders:order_detail', args=[self.pedido_a1.order_number]))
        self.assertEqual(response.status_code, 200)


class PolicyPagesTestCase(TestCase):
    def test_las_paginas_de_politicas_responden_200(self):
        urls = [
            reverse('politica_cambios'),
            reverse('politica_devoluciones'),
            reverse('politica_garantia'),
            reverse('politica_tratamiento_datos'),
            reverse('politica_envios'),
            reverse('politica_pagos'),
            reverse('politica_privacidad'),
            reverse('terminos'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_las_paginas_de_politicas_son_publicas(self):
        # Contenido MOCK: no deben exigir sesion iniciada.
        response = self.client.get(reverse('politica_cambios'))
        self.assertEqual(response.status_code, 200)

    def test_marca_el_contenido_como_provisional(self):
        response = self.client.get(reverse('politica_cambios'))
        self.assertContains(response, 'provisional')

    def test_footer_enlaza_las_politicas(self):
        # home.html deja el bloque footer vacio (es la pagina hero sin
        # navbar/footer); se usa una pagina que si hereda el footer comun.
        response = self.client.get(reverse('acerca_de'))
        for url_name in ['politica_cambios', 'politica_devoluciones', 'politica_garantia',
                          'politica_tratamiento_datos']:
            self.assertContains(response, reverse(url_name))

    def test_footer_ya_no_enlaza_envios_ni_pagos(self):
        # Envios y Pagos se retiraron del footer global: son informacion de
        # soporte al pedido (consulta puntual), no navegacion permanente de
        # marca, y competian por atencion con el resto de politicas. Las
        # paginas se conservan: siguen alcanzables desde el checkout (aviso
        # de consentimiento) y desde el nav propio de las paginas legales
        # (_legal_nav.html), asi que esto no las vuelve inaccesibles.
        response = self.client.get(reverse('acerca_de'))
        self.assertNotContains(response, reverse('politica_envios'))
        self.assertNotContains(response, reverse('politica_pagos'))

    def test_checkout_enlaza_politicas_relevantes(self):
        User = get_user_model()
        usuario = User.objects.create_user(
            email='checkout-policies@example.com', username='checkout-policies@example.com',
            password='secret123',
        )
        categoria = ProductCategory.objects.create(name='Categoria checkout policies')
        marca = Brand.objects.create(name='Marca checkout policies')
        producto = Product.objects.create(
            name='Producto checkout policies', category=categoria, brand=marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        variante = _crear_variante(producto, 'POL-001-S-NEG', 'S', 'negro', 5)

        self.client.force_login(usuario)
        session = self.client.session
        session['cart'] = {str(variante.pk): 1}
        session['cart_version'] = 2
        session.save()

        response = self.client.get(reverse('orders:checkout'))
        self.assertContains(response, reverse('politica_cambios'))
        self.assertContains(response, reverse('politica_devoluciones'))
