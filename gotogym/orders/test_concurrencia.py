"""Carreras entre peticiones simultaneas que SQLite no puede reproducir.

Necesitan bloqueo de fila real, asi que solo corren en motores que lo
implementan (PostgreSQL en el CI; ver `settings_test_postgres`). En SQLite se
omiten: `select_for_update` no hace nada alli.
"""
import threading
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory

from . import services
from .models import Coupon, Order, OrderStatus, OrderStatusHistory
from .services import CheckoutError, confirm_payment, create_order_from_cart
from .test_confirm_payment import DATOS, _crear_variante, _FakeTransaction


def _en_hilos(*tareas):
    """Ejecuta cada tarea en su propio hilo y devuelve lo que cada una
    devolvio o la excepcion que lanzo, en el mismo orden."""
    resultados = [None] * len(tareas)

    def correr(indice, tarea):
        try:
            resultados[indice] = tarea()
        except Exception as error:
            resultados[indice] = error
        finally:
            connections.close_all()

    hilos = [threading.Thread(target=correr, args=(i, t)) for i, t in enumerate(tareas)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
        assert not hilo.is_alive(), 'un hilo no termino: posible bloqueo mutuo'
    return resultados


@skipUnlessDBFeature('has_select_for_update')
class DobleAvisoDePagoTests(TransactionTestCase):
    """El proveedor reenvia avisos: dos llegando a la vez para el mismo
    pedido deben descontar el stock una sola vez."""

    def setUp(self):
        categoria = ProductCategory.objects.create(name='Categoria doble aviso')
        marca = Brand.objects.create(name='Marca doble aviso')
        producto = Product.objects.create(
            name='Producto doble aviso', category=categoria, brand=marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        self.variante = _crear_variante(producto, 'DOBLE-AVISO-S-NEG', 'S', 'negro', 5)
        self.usuario = get_user_model().objects.create_user(
            email='doble-aviso@example.com', username='doble-aviso@example.com', password='secret123',
        )
        self.pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 2}, DATOS)

    def _confirmar(self):
        pedido = Order.objects.get(pk=self.pedido.pk)
        with transaction.atomic():
            confirm_payment(pedido, _FakeTransaction('approved'))

    def test_el_stock_se_descuenta_una_sola_vez(self):
        resultados = _en_hilos(self._confirmar, self._confirmar)

        self.assertEqual([r for r in resultados if isinstance(r, Exception)], [])
        self.assertEqual(Inventory.objects.get(variant=self.variante).quantity_available, 3)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.CONFIRMED)
        confirmaciones = OrderStatusHistory.objects.filter(
            order=self.pedido, to_status=OrderStatus.CONFIRMED,
        ).count()
        self.assertEqual(confirmaciones, 1)


@skipUnlessDBFeature('has_select_for_update')
class UsoSimultaneoDeUnCuponTests(TransactionTestCase):
    def setUp(self):
        categoria = ProductCategory.objects.create(name='Categoria cupon')
        marca = Brand.objects.create(name='Marca cupon')
        producto = Product.objects.create(
            name='Producto cupon', category=categoria, brand=marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        self.variante = _crear_variante(producto, 'CUPON-S-NEG', 'S', 'negro', 10)
        Usuario = get_user_model()
        self.usuarios = [
            Usuario.objects.create_user(email=f'cupon-{n}@example.com', username=f'cupon-{n}', password='x')
            for n in range(2)
        ]
        self.cupon = Coupon.objects.create(code='UNICO', value=Decimal('10'), max_uses=1)

    def test_con_un_solo_uso_disponible_solo_un_pedido_lo_aplica(self):
        # Las dos compras leen el cupon con un uso libre antes de que
        # cualquiera escriba: la barrera fuerza justo esa intercalacion.
        barrera = threading.Barrier(2, timeout=15)
        leer_cupon = services.get_usable_coupon

        def leer_y_esperar(codigo, user=None):
            cupon = leer_cupon(codigo, user=user)
            barrera.wait()
            return cupon

        def comprar(usuario):
            return lambda: create_order_from_cart(
                usuario, {str(self.variante.pk): 1}, {**DATOS, 'coupon_code': 'UNICO'},
            )

        with patch('orders.services.get_usable_coupon', leer_y_esperar):
            resultados = _en_hilos(*(comprar(u) for u in self.usuarios))

        errores = [r for r in resultados if isinstance(r, CheckoutError)]
        pedidos = [r for r in resultados if isinstance(r, Order)]
        self.assertEqual((len(pedidos), len(errores)), (1, 1), resultados)
        self.cupon.refresh_from_db()
        self.assertEqual(self.cupon.times_used, 1)
        self.assertEqual(Order.objects.filter(coupon=self.cupon).count(), 1)
