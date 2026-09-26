"""Sprint de hardening: auditoria de lo construido en checkout/pagos/inventario.

No introduce dominio nuevo; cierra los tests explicitamente pedidos que no
quedaban ya cubiertos por los sprints anteriores.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from inventory.models import Inventory
from payments.models import PaymentTransaction
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


class ManipulacionDirectaDeCarritoTests(TestCase):
    """Manipular variant_id/cantidad via peticion directa nunca produce un
    total distinto al recalculado server-side."""

    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria manipulacion')
        marca = Brand.objects.create(name='Marca manipulacion')
        cls.producto = Product.objects.create(
            name='Producto manipulacion', category=categoria, brand=marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        cls.variante = _crear_variante(cls.producto, 'HARD-001-S-NEG', 'S', 'negro', 3)

    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            email=f'hard-{self._testMethodName[:20]}@example.com',
            username=f'hard-{self._testMethodName[:20]}@example.com',
            password='secret123',
        )
        self.client.force_login(self.usuario)

    def test_no_existe_ningun_campo_de_precio_enviable_en_add_to_cart(self):
        # No hay ningun formulario de la tienda que pida un precio: el unico
        # dato que el cliente controla es la cantidad, y esta se valida
        # contra el inventario real, nunca contra lo que el cliente declare.
        response = self.client.post(
            reverse('carrito:add_to_cart', args=[self.variante.pk]),
            {'price': '1', 'unit_price': '1', 'amount': '1'},
        )
        self.assertEqual(response.status_code, 302)

        detalle = self.client.get(reverse('carrito:cart_detail'))
        # El precio mostrado es el real de la variante, no "1".
        self.assertContains(detalle, '50.000')
        self.assertNotContains(detalle, '$1<')

    def test_manipular_cantidad_por_encima_del_stock_no_cambia_el_total_cobrado(self):
        self.client.post(reverse('carrito:add_to_cart', args=[self.variante.pk]))
        # Intento directo de forzar una cantidad absurda saltandose el CTA.
        self.client.post(
            reverse('carrito:update_cart', args=[self.variante.pk]),
            {'cantidad': '99999'},
        )

        self.client.post(reverse('orders:checkout'), DATOS)
        from orders.models import Order
        pedido = Order.objects.filter(user=self.usuario).first()
        # O no se creo pedido (rechazado por falta de stock), o si se creo
        # el total corresponde exactamente a lo que habia en el carrito
        # antes del intento de manipulacion (1 unidad), nunca a 99999.
        if pedido:
            self.assertEqual(pedido.items.get().quantity, 1)
            self.assertEqual(pedido.subtotal, Decimal('50000.00'))

    def test_variant_id_inexistente_en_add_to_cart_da_404_no_500(self):
        response = self.client.post(reverse('carrito:add_to_cart', args=[999999]))
        self.assertEqual(response.status_code, 404)


class DobleSubmitDeConfirmacionTests(TestCase):
    """Reafirma explicitamente el test critico: doble-submit de confirmacion
    de pago no descuenta stock dos veces, a nivel de la vista completa."""

    def setUp(self):
        categoria = ProductCategory.objects.create(name='Categoria doble submit')
        marca = Brand.objects.create(name='Marca doble submit')
        producto = Product.objects.create(
            name='Producto doble submit', category=categoria, brand=marca,
            base_price=Decimal('40000.0000'), stock=0,
        )
        self.variante = _crear_variante(producto, 'HARD-002-S-NEG', 'S', 'negro', 5)

        User = get_user_model()
        self.usuario = User.objects.create_user(
            email='doble-submit@example.com', username='doble-submit@example.com', password='secret123',
        )
        self.pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 2}, DATOS)
        self.client.force_login(self.usuario)

    @override_settings(DEBUG=True)
    def test_doble_clic_en_simular_aprobado_no_duplica_el_descuento(self):
        url = reverse('payments:simulate', args=[self.pedido.order_number, 'approved'])
        self.client.post(url)
        self.client.post(url)

        self.assertEqual(Inventory.objects.get(variant=self.variante).quantity_available, 3)
        self.assertEqual(PaymentTransaction.objects.filter(order=self.pedido).count(), 1)


class RateLimitDeEndpointsSensiblesTests(TestCase):
    """add_to_cart y payments:simulate estan protegidos contra abuso trivial."""

    def setUp(self):
        cache.clear()
        categoria = ProductCategory.objects.create(name='Categoria rate limit')
        marca = Brand.objects.create(name='Marca rate limit')
        producto = Product.objects.create(
            name='Producto rate limit', category=categoria, brand=marca,
            base_price=Decimal('30000.0000'), stock=0,
        )
        self.variante = _crear_variante(producto, 'HARD-003-S-NEG', 'S', 'negro', 1000)

        User = get_user_model()
        self.usuario = User.objects.create_user(
            email='ratelimit@example.com', username='ratelimit@example.com', password='secret123',
        )
        self.client.force_login(self.usuario)

    def tearDown(self):
        cache.clear()

    def test_add_to_cart_se_bloquea_tras_muchos_intentos_seguidos(self):
        url = reverse('carrito:add_to_cart', args=[self.variante.pk])
        codigos = [self.client.post(url).status_code for _ in range(35)]
        self.assertIn(429, codigos)

    @override_settings(DEBUG=True)
    def test_payment_simulate_se_bloquea_tras_muchos_intentos_seguidos(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        url = reverse('payments:simulate', args=[pedido.order_number, 'pending'])
        codigos = [self.client.post(url).status_code for _ in range(25)]
        self.assertIn(429, codigos)
