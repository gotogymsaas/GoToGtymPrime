"""Panel admin de pedidos y pagos: transiciones validas, proteccion de
payment_status y permisos."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Inventory
from orders.models import Order, OrderStatus, PaymentStatus
from orders.services import (
    InvalidOrderTransitionError,
    apply_order_status_transition,
    create_order_from_cart,
    valid_next_statuses,
)
from payments.models import PaymentTransaction
from products.models import Brand, Product, ProductCategory, ProductVariant

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class OrderTransitionServiceTests(TestCase):
    """Reglas de transicion, independientes de la vista de admin."""

    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria transiciones')
        marca = Brand.objects.create(name='Marca transiciones')
        producto = Product.objects.create(
            name='Producto transiciones', category=categoria, brand=marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        variante = _crear_variante(producto, 'ADM-001-S-NEG', 'S', 'negro', 5)
        User = get_user_model()
        usuario = User.objects.create_user(
            email='admin-transiciones@example.com', username='admin-transiciones@example.com',
            password='secret123',
        )
        cls.pedido = create_order_from_cart(usuario, {str(variante.pk): 1}, DATOS)

    def test_pending_payment_no_puede_saltar_directo_a_delivered(self):
        with self.assertRaises(InvalidOrderTransitionError):
            apply_order_status_transition(self.pedido, OrderStatus.DELIVERED)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.PENDING_PAYMENT)

    def test_pending_payment_no_puede_confirmarse_sin_pago_aprobado(self):
        self.assertNotIn(OrderStatus.CONFIRMED, valid_next_statuses(self.pedido))
        with self.assertRaises(InvalidOrderTransitionError):
            apply_order_status_transition(self.pedido, OrderStatus.CONFIRMED)

    def test_puede_confirmarse_si_el_pago_ya_esta_aprobado(self):
        self.pedido.payment_status = PaymentStatus.APPROVED
        self.pedido.save(update_fields=['payment_status'])
        self.assertIn(OrderStatus.CONFIRMED, valid_next_statuses(self.pedido))

        apply_order_status_transition(self.pedido, OrderStatus.CONFIRMED)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.CONFIRMED)

    def test_avance_paso_a_paso_hasta_delivered(self):
        self.pedido.payment_status = PaymentStatus.APPROVED
        self.pedido.save(update_fields=['payment_status'])

        secuencia = [
            OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.SHIPPED,
            OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED,
        ]
        for estado in secuencia:
            apply_order_status_transition(self.pedido, estado)
            self.pedido.refresh_from_db()
            self.assertEqual(self.pedido.order_status, estado)

    def test_no_se_puede_saltar_de_confirmed_a_shipped(self):
        self.pedido.payment_status = PaymentStatus.APPROVED
        self.pedido.order_status = OrderStatus.CONFIRMED
        self.pedido.save(update_fields=['payment_status', 'order_status'])

        with self.assertRaises(InvalidOrderTransitionError):
            apply_order_status_transition(self.pedido, OrderStatus.SHIPPED)

    def test_delivered_no_tiene_transiciones_posteriores(self):
        self.pedido.payment_status = PaymentStatus.APPROVED
        self.pedido.order_status = OrderStatus.DELIVERED
        self.pedido.save(update_fields=['payment_status', 'order_status'])
        self.assertEqual(valid_next_statuses(self.pedido), [])

    def test_cancelado_no_tiene_transiciones_posteriores(self):
        self.pedido.order_status = OrderStatus.CANCELLED
        self.pedido.save(update_fields=['order_status'])
        self.assertEqual(valid_next_statuses(self.pedido), [])

    def test_no_se_puede_cancelar_un_pedido_ya_enviado(self):
        self.pedido.payment_status = PaymentStatus.APPROVED
        self.pedido.order_status = OrderStatus.SHIPPED
        self.pedido.save(update_fields=['payment_status', 'order_status'])
        self.assertNotIn(OrderStatus.CANCELLED, valid_next_statuses(self.pedido))

    def test_transicion_valida_no_toca_payment_status(self):
        self.pedido.payment_status = PaymentStatus.APPROVED
        self.pedido.save(update_fields=['payment_status'])
        apply_order_status_transition(self.pedido, OrderStatus.CONFIRMED)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.payment_status, PaymentStatus.APPROVED)


class AdminOrdersAccessTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria admin pedidos')
        cls.marca = Brand.objects.create(name='Marca admin pedidos')
        cls.producto = Product.objects.create(
            name='Producto admin pedidos', category=cls.categoria, brand=cls.marca,
            base_price=Decimal('80000.0000'), stock=0,
        )
        cls.variante = _crear_variante(cls.producto, 'ADM-002-S-NEG', 'S', 'negro', 5)

        User = get_user_model()
        cls.cliente = User.objects.create_user(
            email='cliente-admin@example.com', username='cliente-admin@example.com', password='secret123',
        )
        cls.staff = User.objects.create_user(
            email='staff-admin@example.com', username='staff-admin@example.com', password='secret123',
            is_staff=True,
        )
        cls.pedido = create_order_from_cart(cls.cliente, {str(cls.variante.pk): 1}, DATOS)

    def _urls(self):
        return [
            reverse('admin_orders'),
            reverse('admin_order_detail', args=[self.pedido.order_number]),
            reverse('admin_payment_transactions'),
        ]

    def test_anonimo_no_accede_a_ninguna_vista(self):
        for url in self._urls():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)

    def test_cliente_no_staff_no_accede(self):
        self.client.force_login(self.cliente)
        for url in self._urls():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)

    def test_staff_accede_a_las_tres_vistas(self):
        self.client.force_login(self.staff)
        for url in self._urls():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_actualizar_estado_exige_staff(self):
        url = reverse('admin_order_update_status', args=[self.pedido.order_number])
        response = self.client.post(url, {'order_status': OrderStatus.CANCELLED})
        self.assertEqual(response.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.PENDING_PAYMENT)


class AdminCannotEditPaymentStatusTests(TestCase):
    """El formulario de admin nunca puede cambiar payment_status, ni
    aunque el POST lo incluya manipulado a mano."""

    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria payment status')
        marca = Brand.objects.create(name='Marca payment status')
        producto = Product.objects.create(
            name='Producto payment status', category=categoria, brand=marca,
            base_price=Decimal('60000.0000'), stock=0,
        )
        variante = _crear_variante(producto, 'ADM-003-S-NEG', 'S', 'negro', 5)

        User = get_user_model()
        cliente = User.objects.create_user(
            email='cliente-pago@example.com', username='cliente-pago@example.com', password='secret123',
        )
        cls.staff = User.objects.create_user(
            email='staff-pago@example.com', username='staff-pago@example.com', password='secret123',
            is_staff=True,
        )
        cls.pedido = create_order_from_cart(cliente, {str(variante.pk): 1}, DATOS)

    def test_intentar_enviar_payment_status_no_lo_modifica(self):
        self.client.force_login(self.staff)
        url = reverse('admin_order_update_status', args=[self.pedido.order_number])

        # No hay transicion valida desde pending_payment salvo cancelar; se
        # incluye payment_status manipulado para confirmar que el servidor
        # lo ignora incluso cuando la transicion de order_status si aplica.
        self.client.post(url, {
            'order_status': OrderStatus.CANCELLED,
            'payment_status': PaymentStatus.APPROVED,
        })

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.CANCELLED)
        self.assertEqual(self.pedido.payment_status, PaymentStatus.PENDING)

    def test_el_campo_payment_status_no_es_editable_en_el_formulario(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin_order_detail', args=[self.pedido.order_number]))
        self.assertNotContains(response, 'name="payment_status"')


class PaymentTransactionsListTests(TestCase):
    def test_lista_transacciones_de_distintos_pedidos(self):
        categoria = ProductCategory.objects.create(name='Categoria pagos admin')
        marca = Brand.objects.create(name='Marca pagos admin')
        producto = Product.objects.create(
            name='Producto pagos admin', category=categoria, brand=marca,
            base_price=Decimal('40000.0000'), stock=0,
        )
        variante = _crear_variante(producto, 'ADM-004-S-NEG', 'S', 'negro', 5)

        User = get_user_model()
        cliente = User.objects.create_user(
            email='cliente-lista-pagos@example.com', username='cliente-lista-pagos@example.com',
            password='secret123',
        )
        staff = User.objects.create_user(
            email='staff-lista-pagos@example.com', username='staff-lista-pagos@example.com',
            password='secret123', is_staff=True,
        )
        pedido = create_order_from_cart(cliente, {str(variante.pk): 1}, DATOS)
        PaymentTransaction.objects.create(
            order=pedido, provider='mock', preference_id='pref-test-1',
            external_reference=pedido.order_number, status='pending',
            amount=pedido.total, idempotency_key='idem-test-1',
        )

        self.client.force_login(staff)
        response = self.client.get(reverse('admin_payment_transactions'))
        self.assertContains(response, 'pref-test-1')
        self.assertContains(response, pedido.order_number)
