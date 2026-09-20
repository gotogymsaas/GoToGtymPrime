"""Operaciones de stock sobre `Inventory`.

`decrement_stock` y `restore_stock` reciben una lista de pares
`(variant, quantity)` en vez de una orden concreta: todavia no existe un
modelo de pedido en el dominio, y esta forma es la que un futuro llamador
(la confirmacion de un pedido) puede construir sin que este modulo conozca
nada de pedidos.

El descuento se protege por dos vias complementarias:

1. `select_for_update()` serializa las transacciones que compiten por las
   mismas filas. Es la proteccion real en PostgreSQL y MySQL.
2. Un UPDATE condicional (`quantity_available >= cantidad`) que decide en el
   propio motor si el descuento cabe. Esto es lo que evita sobreventa en
   SQLite, donde `select_for_update()` no hace nada.
"""
from collections import OrderedDict

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Inventory


class InsufficientStockError(Exception):
    """Se lanza cuando no hay stock suficiente para completar un descuento.

    No queda ningun registro modificado: la transaccion que envuelve la
    llamada hace rollback completo.
    """

    def __init__(self, variant, requested, available):
        self.variant = variant
        self.requested = requested
        self.available = available
        super().__init__(
            f"Stock insuficiente para {variant.sku}: se pidieron {requested}, "
            f"hay {available} disponibles."
        )


def get_available_quantity(variant):
    """Cantidad disponible leida de la base de datos.

    Se consulta explicitamente en vez de usar `variant.inventory` porque esa
    relacion queda cacheada en la instancia y no refleja los descuentos
    hechos con UPDATE.
    """
    quantity = (
        Inventory.objects
        .filter(variant_id=variant.id)
        .values_list('quantity_available', flat=True)
        .first()
    )
    return 0 if quantity is None else quantity


def check_availability(variant, quantity):
    """Lectura simple, sin lock: para pintar disponibilidad en catalogo/PDP.

    No da ninguna garantia frente a compras concurrentes; la unica
    verificacion que decide de verdad ocurre dentro de `decrement_stock`.
    """
    if quantity <= 0:
        return True
    return get_available_quantity(variant) >= quantity


def _normalize(items):
    """Agrupa cantidades por variante y ordena por id.

    Agrupar evita que la misma variante repetida se valide dos veces por
    separado; ordenar hace que dos transacciones concurrentes tomen los
    bloqueos siempre en el mismo orden, de modo que no puedan quedarse
    esperandose mutuamente.
    """
    grouped = OrderedDict()
    for variant, quantity in items:
        if quantity <= 0:
            continue
        if variant.id in grouped:
            existing_variant, existing_quantity = grouped[variant.id]
            grouped[variant.id] = (existing_variant, existing_quantity + quantity)
        else:
            grouped[variant.id] = (variant, quantity)
    return [grouped[key] for key in sorted(grouped)]


def _lock_rows(variant_ids):
    # En SQLite no hace nada; la correccion no depende de esto (ver el UPDATE
    # condicional de decrement_stock), pero en PostgreSQL/MySQL serializa a
    # las transacciones que compiten por las mismas variantes.
    list(Inventory.objects.select_for_update().filter(variant_id__in=variant_ids).order_by('variant_id'))


@transaction.atomic
def decrement_stock(items):
    """Descuenta `quantity` unidades de cada `(variant, quantity)`.

    Todo o nada: si alguna variante no tiene stock suficiente se lanza
    `InsufficientStockError` y la transaccion revierte los descuentos ya
    aplicados dentro de la misma llamada.
    """
    normalized = _normalize(items)
    if not normalized:
        return

    _lock_rows([variant.id for variant, _ in normalized])

    now = timezone.now()
    for variant, quantity in normalized:
        updated = Inventory.objects.filter(
            variant_id=variant.id,
            quantity_available__gte=quantity,
        ).update(
            quantity_available=F('quantity_available') - quantity,
            updated_at=now,
        )
        if not updated:
            raise InsufficientStockError(variant, quantity, get_available_quantity(variant))


@transaction.atomic
def restore_stock(items):
    """Repone `quantity` unidades de cada `(variant, quantity)`.

    Para cancelaciones posteriores a un descuento ya aplicado; no forma parte
    del flujo normal de compra.
    """
    normalized = _normalize(items)
    if not normalized:
        return

    _lock_rows([variant.id for variant, _ in normalized])

    now = timezone.now()
    for variant, quantity in normalized:
        Inventory.objects.filter(variant_id=variant.id).update(
            quantity_available=F('quantity_available') + quantity,
            updated_at=now,
        )
