"""Ayudas para armar catalogos de prueba del vendedor. No contiene pruebas."""
from decimal import Decimal

from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

_contador = {'sku': 0}


def aislar_catalogo():
    """La base de pruebas parte con el catalogo semilla de las migraciones.
    Desactivar sus variantes lo saca de la tienda (un producto sin variantes
    activas no se muestra) sin borrar nada, y la transaccion de cada prueba
    lo deshace al terminar."""
    ProductVariant.objects.update(is_active=False)


def crear_producto(nombre, variantes, descripcion='', categoria='Prendas', marca='Marca', **campos):
    """Crea un producto con sus variantes.

    `variantes` es una lista de `(talla, color, stock)` o
    `(talla, color, stock, opciones)` con `opciones` para `price_override`,
    `discount_price` o `is_active`. Devuelve `(producto, [variantes])`."""
    categoria_obj, _ = ProductCategory.objects.get_or_create(name=categoria)
    marca_obj, _ = Brand.objects.get_or_create(name=marca)
    campos.setdefault('base_price', Decimal('100000.0000'))
    producto = Product.objects.create(
        name=nombre, category=categoria_obj, brand=marca_obj, description=descripcion, **campos,
    )
    creadas = []
    for definicion in variantes:
        talla, color, stock = definicion[:3]
        opciones = definicion[3] if len(definicion) > 3 else {}
        _contador['sku'] += 1
        variante = ProductVariant.objects.create(
            product=producto, sku=f'T-{_contador["sku"]:05d}', size=talla, color=color, **opciones,
        )
        Inventory.objects.create(variant=variante, quantity_available=stock)
        creadas.append(variante)
    return producto, creadas
