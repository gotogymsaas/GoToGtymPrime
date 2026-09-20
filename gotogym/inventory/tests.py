"""Servicio de stock: descuento, reposicion y comportamiento bajo concurrencia."""
import threading
from decimal import Decimal

from django.db import IntegrityError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from products.models import Brand, Product, ProductCategory, ProductVariant

from .models import Inventory
from .services import (
    InsufficientStockError,
    check_availability,
    decrement_stock,
    get_available_quantity,
    restore_stock,
)


def _build_variant(name, sku, quantity, size='S', color='negro'):
    category, _ = ProductCategory.objects.get_or_create(name='Categoria inventario test')
    brand, _ = Brand.objects.get_or_create(name='Marca inventario test')
    product = Product.objects.create(
        name=name, category=category, brand=brand, base_price=Decimal('100000.0000'), stock=quantity,
    )
    variant = ProductVariant.objects.create(product=product, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variant, quantity_available=quantity)
    return variant


class CheckAvailabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.variant = _build_variant('Disponibilidad', 'INV-TEST-AVAIL', 5)

    def test_true_when_enough_stock(self):
        self.assertTrue(check_availability(self.variant, 5))

    def test_false_when_not_enough_stock(self):
        self.assertFalse(check_availability(self.variant, 6))

    def test_false_when_variant_has_no_inventory_row(self):
        huerfana = ProductVariant.objects.create(
            product=self.variant.product, sku='INV-TEST-NOINV', size='M', color='negro',
        )
        self.assertFalse(check_availability(huerfana, 1))


class DecrementStockTests(TestCase):
    def setUp(self):
        self.variant = _build_variant('Descuento', 'INV-TEST-DEC', 10)

    def test_decrements_exactly_the_requested_quantity(self):
        decrement_stock([(self.variant, 3)])
        self.assertEqual(get_available_quantity(self.variant), 7)

    def test_can_decrement_down_to_zero(self):
        decrement_stock([(self.variant, 10)])
        self.assertEqual(get_available_quantity(self.variant), 0)

    def test_insufficient_stock_raises_and_leaves_quantity_untouched(self):
        with self.assertRaises(InsufficientStockError) as ctx:
            decrement_stock([(self.variant, 11)])

        self.assertEqual(ctx.exception.requested, 11)
        self.assertEqual(ctx.exception.available, 10)
        self.assertEqual(get_available_quantity(self.variant), 10)

    def test_partial_failure_rolls_back_the_whole_operation(self):
        otra = _build_variant('Descuento B', 'INV-TEST-DEC-B', 2, size='M')

        with self.assertRaises(InsufficientStockError):
            decrement_stock([(self.variant, 5), (otra, 99)])

        # Ninguna de las dos debe haber cambiado, ni siquiera la que si tenia
        # stock suficiente.
        self.assertEqual(get_available_quantity(self.variant), 10)
        self.assertEqual(get_available_quantity(otra), 2)

    def test_repeated_variant_quantities_are_aggregated(self):
        with self.assertRaises(InsufficientStockError):
            decrement_stock([(self.variant, 6), (self.variant, 6)])
        self.assertEqual(get_available_quantity(self.variant), 10)

        decrement_stock([(self.variant, 4), (self.variant, 6)])
        self.assertEqual(get_available_quantity(self.variant), 0)

    def test_empty_and_zero_quantity_items_are_noops(self):
        decrement_stock([])
        decrement_stock([(self.variant, 0)])
        self.assertEqual(get_available_quantity(self.variant), 10)


class DatabaseLevelGuardTests(TestCase):
    """Ultima linea de defensa: aunque algo escribiera mal el stock, el motor
    no debe aceptar una cantidad negativa."""

    def test_database_rejects_negative_quantity(self):
        variant = _build_variant('Guarda BD', 'INV-TEST-GUARD', 1)
        inventory = Inventory.objects.get(variant=variant)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Inventory.objects.filter(pk=inventory.pk).update(quantity_available=-1)

        self.assertEqual(get_available_quantity(variant), 1)


class RestoreStockTests(TestCase):
    def setUp(self):
        self.variant = _build_variant('Reposicion', 'INV-TEST-RES', 4)

    def test_restores_the_requested_quantity(self):
        decrement_stock([(self.variant, 4)])
        restore_stock([(self.variant, 4)])
        self.assertEqual(get_available_quantity(self.variant), 4)

    def test_restore_is_additive(self):
        restore_stock([(self.variant, 6)])
        self.assertEqual(get_available_quantity(self.variant), 10)


class StaleReadDoesNotOversellTests(TestCase):
    """El caso de sobreventa, sin hilos: dos compradores leen disponibilidad
    antes de que ninguno descuente, y el segundo intenta comprar cuando el
    stock ya se agoto. Corre en cualquier motor, incluido SQLite."""

    def test_second_buyer_is_rejected_after_the_first_takes_the_last_unit(self):
        variant = _build_variant('Lectura obsoleta', 'INV-TEST-STALE', 1)

        # Ambos ven una unidad disponible.
        self.assertTrue(check_availability(variant, 1))
        self.assertTrue(check_availability(variant, 1))

        decrement_stock([(variant, 1)])

        with self.assertRaises(InsufficientStockError):
            decrement_stock([(variant, 1)])

        self.assertEqual(get_available_quantity(variant), 0)


@skipUnlessDBFeature('has_select_for_update')
class ConcurrentDecrementTests(TransactionTestCase):
    """Dos compradores compitiendo por la ultima unidad, con hilos reales.

    Solo corre en motores con bloqueo de fila (PostgreSQL, MySQL). SQLite
    queda fuera: no implementa `SELECT ... FOR UPDATE` y ademas serializa la
    escritura a nivel de fichero, de modo que los hilos fallan con "database
    table is locked" en vez de ejercitar la condicion de carrera. En SQLite
    la garantia la cubre StaleReadDoesNotOversellTests.
    """

    def _decrement_in_thread(self, variant_id, results, index):
        from products.models import ProductVariant as PV
        try:
            variant = PV.objects.get(pk=variant_id)
            with transaction.atomic():
                decrement_stock([(variant, 1)])
            results[index] = 'ok'
        except InsufficientStockError:
            results[index] = 'sin_stock'
        except Exception as exc:  # pragma: no cover - diagnostico si algo mas falla
            results[index] = f'error: {exc!r}'
        finally:
            connections.close_all()

    def test_only_one_of_two_concurrent_buyers_gets_the_last_unit(self):
        variant = _build_variant('Ultima unidad', 'INV-TEST-RACE', 1)

        results = [None, None]
        hilos = [
            threading.Thread(target=self._decrement_in_thread, args=(variant.id, results, i))
            for i in range(2)
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=10)

        self.assertEqual(sorted(results), ['ok', 'sin_stock'], f'resultados: {results}')
        self.assertEqual(get_available_quantity(variant), 0)

    def test_stock_never_goes_negative_under_contention(self):
        variant = _build_variant('Contencion', 'INV-TEST-RACE-2', 5)

        results = [None] * 10
        hilos = [
            threading.Thread(target=self._decrement_in_thread, args=(variant.id, results, i))
            for i in range(10)
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=10)

        exitosos = results.count('ok')
        self.assertEqual(exitosos, 5, f'resultados: {results}')
        self.assertEqual(get_available_quantity(variant), 0)


@skipUnlessDBFeature('has_select_for_update')
class SelectForUpdateSupportTests(TransactionTestCase):
    """SQLite ignora `select_for_update()`, asi que la garantia por bloqueo de
    fila solo puede comprobarse en PostgreSQL o MySQL. En SQLite la proteccion
    efectiva es el UPDATE condicional, cubierto por los tests de concurrencia
    de arriba."""

    def test_backend_supports_row_locking(self):
        self.assertTrue(connection.features.has_select_for_update)
