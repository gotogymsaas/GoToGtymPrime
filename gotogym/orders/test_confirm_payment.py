"""Confirmacion de pago -> descuento de inventario -> recibo.

Cubre los cinco tests criticos del dominio transaccional:
1. Pago pendiente -> stock intacto.
2. Pago rechazado -> stock intacto, order_status nunca avanza a confirmed.
3. Pago aprobado -> stock descontado exactamente.
4. Stock insuficiente al aprobar -> el pedido no queda confirmado a medias.
5. Concurrencia -> dos ordenes compitiendo por la ultima unidad, solo una
   descuenta con exito.
"""
import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

from .models import Order, OrderStatus, PaymentStatus
from .services import PaymentNotApprovedError, confirm_payment, create_order_from_cart

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class _FakeTransaction:
    """Doble minimo de PaymentTransaction: confirm_payment solo mira `.status`."""

    def __init__(self, status):
        self.status = status


class ConfirmPaymentBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria confirm')
        cls.marca = Brand.objects.create(name='Marca confirm')
        cls.producto = Product.objects.create(
            name='Producto confirm', category=cls.categoria, brand=cls.marca,
            base_price=Decimal('100000.0000'), stock=0,
        )
        cls.variante = _crear_variante(cls.producto, 'CONF-001-S-NEG', 'S', 'negro', 5)

    def setUp(self):
        super().setUp()
        User = get_user_model()
        correo = f'confirm-{self._testMethodName[:30]}@example.com'
        self.usuario = User.objects.create_user(email=correo, username=correo, password='secret123')

    def _crear_pedido(self, cantidad=2):
        return create_order_from_cart(self.usuario, {str(self.variante.pk): cantidad}, DATOS)

    def _stock(self):
        return Inventory.objects.get(variant=self.variante).quantity_available


class Test1PagoPendienteStockIntacto(ConfirmPaymentBaseTestCase):
    def test_pago_pendiente_no_descuenta_stock(self):
        self._crear_pedido(2)
        # No se llama confirm_payment: un pago pendiente no dispara nada.
        self.assertEqual(self._stock(), 5)

    def test_pago_pendiente_no_puede_confirmarse(self):
        pedido = self._crear_pedido(2)
        with self.assertRaises(PaymentNotApprovedError):
            confirm_payment(pedido, _FakeTransaction('pending'))
        self.assertEqual(self._stock(), 5)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.PENDING_PAYMENT)


class Test2PagoRechazadoStockIntacto(ConfirmPaymentBaseTestCase):
    def test_pago_rechazado_no_descuenta_stock_ni_avanza_la_orden(self):
        pedido = self._crear_pedido(2)

        with self.assertRaises(PaymentNotApprovedError):
            confirm_payment(pedido, _FakeTransaction('rejected'))

        self.assertEqual(self._stock(), 5)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.PENDING_PAYMENT)
        self.assertNotEqual(pedido.order_status, OrderStatus.CONFIRMED)


class Test3PagoAprobadoDescuentaExacto(ConfirmPaymentBaseTestCase):
    def test_pago_aprobado_descuenta_exactamente_lo_pedido(self):
        pedido = self._crear_pedido(2)
        confirm_payment(pedido, _FakeTransaction('approved'))

        self.assertEqual(self._stock(), 3)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(pedido.payment_status, PaymentStatus.APPROVED)

    def test_multiples_lineas_descuentan_cada_una_su_propia_variante(self):
        otra_variante = _crear_variante(self.producto, 'CONF-001-M-NEG', 'M', 'negro', 4)
        pedido = create_order_from_cart(
            self.usuario, {str(self.variante.pk): 1, str(otra_variante.pk): 3}, DATOS,
        )
        confirm_payment(pedido, _FakeTransaction('approved'))

        self.assertEqual(self._stock(), 4)
        self.assertEqual(Inventory.objects.get(variant=otra_variante).quantity_available, 1)

    def test_confirmar_dos_veces_no_descuenta_dos_veces(self):
        # Doble aviso de pago (doble clic, webhook duplicado): idempotente.
        pedido = self._crear_pedido(2)
        confirm_payment(pedido, _FakeTransaction('approved'))
        confirm_payment(pedido, _FakeTransaction('approved'))

        self.assertEqual(self._stock(), 3)


class Test4StockInsuficienteAlAprobar(ConfirmPaymentBaseTestCase):
    def test_stock_agotado_entre_checkout_y_aprobacion_no_confirma_a_medias(self):
        pedido = self._crear_pedido(2)

        # Otro comprador se lleva el stock restante despues del checkout,
        # antes de que este pago se apruebe.
        Inventory.objects.filter(variant=self.variante).update(quantity_available=1)

        confirm_payment(pedido, _FakeTransaction('approved'))

        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
        self.assertEqual(pedido.payment_status, PaymentStatus.APPROVED)
        self.assertIn('CONF-001-S-NEG', pedido.internal_note)
        self.assertIn('reembolso manual', pedido.internal_note.lower())

        # No se descuenta parcialmente: el stock que quedaba sigue intacto.
        self.assertEqual(self._stock(), 1)

    def test_variante_eliminada_antes_de_aprobar_tambien_queda_para_revision(self):
        pedido = self._crear_pedido(1)
        self.variante.delete()

        confirm_payment(pedido, _FakeTransaction('approved'))

        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
        self.assertIn('CONF-001-S-NEG', pedido.internal_note)

    def test_no_queda_en_500_ni_a_medias_con_varias_lineas(self):
        otra_variante = _crear_variante(self.producto, 'CONF-001-L-NEG', 'L', 'negro', 5)
        pedido = create_order_from_cart(
            self.usuario, {str(self.variante.pk): 5, str(otra_variante.pk): 1}, DATOS,
        )
        # Se agota justo la primera variante antes de aprobar el pago.
        Inventory.objects.filter(variant=self.variante).update(quantity_available=1)

        confirm_payment(pedido, _FakeTransaction('approved'))

        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CANCELLED)
        # Ninguna de las dos lineas se descuenta: todo o nada.
        self.assertEqual(Inventory.objects.get(variant=otra_variante).quantity_available, 5)


@skipUnlessDBFeature('has_select_for_update')
class Test5ConcurrenciaDosOrdenesUnaSolaGana(TransactionTestCase):
    """Dos ordenes distintas compitiendo por la ultima unidad de la misma
    variante, confirmando el pago casi al mismo tiempo.

    Solo corre en motores con bloqueo de fila real (Postgres/MySQL); en
    SQLite la garantia equivalente se prueba sin hilos en
    ConcurrenciaSecuencialTests, mas abajo.
    """

    def setUp(self):
        self.categoria = ProductCategory.objects.create(name='Categoria concurrencia orden')
        self.marca = Brand.objects.create(name='Marca concurrencia orden')
        self.producto = Product.objects.create(
            name='Producto concurrencia orden', category=self.categoria, brand=self.marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        self.variante = _crear_variante(self.producto, 'CONF-RACE-S-NEG', 'S', 'negro', 1)

        User = get_user_model()
        self.usuario = User.objects.create_user(
            email='race-orders@example.com', username='race-orders@example.com', password='secret123',
        )

        self.pedido_a = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        self.pedido_b = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)

    def _confirmar_en_hilo(self, pedido_id, resultados, indice):
        try:
            pedido = Order.objects.get(pk=pedido_id)
            with transaction.atomic():
                confirm_payment(pedido, _FakeTransaction('approved'))
            pedido.refresh_from_db()
            resultados[indice] = pedido.order_status
        finally:
            connections.close_all()

    def test_solo_una_orden_confirma_la_ultima_unidad(self):
        resultados = [None, None]
        hilos = [
            threading.Thread(target=self._confirmar_en_hilo, args=(self.pedido_a.id, resultados, 0)),
            threading.Thread(target=self._confirmar_en_hilo, args=(self.pedido_b.id, resultados, 1)),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=10)

        self.assertEqual(
            sorted(resultados), [OrderStatus.CANCELLED, OrderStatus.CONFIRMED],
            f'resultados: {resultados}',
        )
        self.assertEqual(Inventory.objects.get(variant=self.variante).quantity_available, 0)


class ConcurrenciaSecuencialTests(TestCase):
    """Version sin hilos del test critico #5: no depende de bloqueo de fila
    real, asi que corre igual en SQLite. Confirma la misma regla de negocio
    (solo una orden se queda con la ultima unidad) sin exigir concurrencia
    real del motor."""

    def test_la_segunda_orden_que_intenta_confirmar_pierde_la_carrera(self):
        categoria = ProductCategory.objects.create(name='Categoria secuencial')
        marca = Brand.objects.create(name='Marca secuencial')
        producto = Product.objects.create(
            name='Producto secuencial', category=categoria, brand=marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        variante = _crear_variante(producto, 'CONF-SEQ-S-NEG', 'S', 'negro', 1)

        User = get_user_model()
        usuario = User.objects.create_user(
            email='seq-orders@example.com', username='seq-orders@example.com', password='secret123',
        )

        pedido_a = create_order_from_cart(usuario, {str(variante.pk): 1}, DATOS)
        pedido_b = create_order_from_cart(usuario, {str(variante.pk): 1}, DATOS)

        confirm_payment(pedido_a, _FakeTransaction('approved'))
        confirm_payment(pedido_b, _FakeTransaction('approved'))

        pedido_a.refresh_from_db()
        pedido_b.refresh_from_db()
        self.assertEqual(pedido_a.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(pedido_b.order_status, OrderStatus.CANCELLED)
        self.assertEqual(Inventory.objects.get(variant=variante).quantity_available, 0)


class IntegracionSimulacionDePagoTests(ConfirmPaymentBaseTestCase):
    """El flujo real: simular 'approved' desde la UI mock dispara
    confirm_payment automaticamente, sin llamarlo a mano."""

    @override_settings(DEBUG=True)
    def test_simular_aprobado_descuenta_stock_a_traves_de_la_vista(self):
        pedido = self._crear_pedido(2)
        self.client.force_login(self.usuario)

        self.client.get(reverse('payments:pending', args=[pedido.order_number]))
        self.client.post(reverse('payments:simulate', args=[pedido.order_number, 'approved']))

        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(self._stock(), 3)

    @override_settings(DEBUG=True)
    def test_simular_rechazado_no_toca_inventario(self):
        pedido = self._crear_pedido(2)
        self.client.force_login(self.usuario)

        self.client.get(reverse('payments:pending', args=[pedido.order_number]))
        self.client.post(reverse('payments:simulate', args=[pedido.order_number, 'rejected']))

        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(pedido.payment_status, PaymentStatus.REJECTED)
        self.assertEqual(self._stock(), 5)

    @override_settings(DEBUG=True)
    def test_recibo_se_ve_en_el_detalle_del_pedido_tras_confirmar(self):
        pedido = self._crear_pedido(1)
        self.client.force_login(self.usuario)
        self.client.post(reverse('payments:simulate', args=[pedido.order_number, 'approved']))

        response = self.client.get(reverse('orders:order_detail', args=[pedido.order_number]))
        self.assertContains(response, 'Confirmado')
        self.assertContains(response, 'Imprimir recibo')
        self.assertContains(response, pedido.order_number)
