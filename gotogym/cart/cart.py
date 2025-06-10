# cart/cart.py
from products.models import Product

CART_SESSION_ID = "cart"


class SessionCart:
    """Carrito guardado en request.session"""

    def __init__(self, request):
        self.session = request.session
        # {'1': 2, '5': 1, ...}
        self.cart: dict[str, int] = self.session.get(CART_SESSION_ID, {})

    # ------------------------------------------------------------------ utils
    def _save(self):
        self.session[CART_SESSION_ID] = self.cart
        self.session.modified = True

    # ---------------------------------------------------------------- actions
    def add(self, product_id: int, qty: int = 1):
        """
        Suma *qty* unidades (puede ser negativa para restar).
        Si el resultado llega a 0 o menos, elimina el producto del carrito.
        """
        pid = str(product_id)
        new_qty = self.cart.get(pid, 0) + qty

        if new_qty > 0:
            self.cart[pid] = new_qty
        else:                          # 0 ó negativo → quitar
            self.cart.pop(pid, None)

        self._save()

    def set(self, product_id: int, qty: int):
        """
        Fija exactamente la cantidad indicada.
        - Si qty > 0 → guarda.
        - Si qty <= 0 → elimina.
        """
        pid = str(product_id)
        if qty > 0:
            self.cart[pid] = qty
        else:
            self.cart.pop(pid, None)

        self._save()

    def remove(self, product_id: int):
        """Elimina el producto, sin importar cuántas unidades tenga."""
        self.cart.pop(str(product_id), None)
        self._save()

    def clear(self):
        """Vacía todo el carrito."""
        self.session[CART_SESSION_ID] = {}
        self.session.modified = True

    # --------------------------------------------------------- helpers/props
    def __iter__(self):
        """
        Itera sobre los items devolviendo:
        {
          'product'  : <Product obj>,
          'qty'      : int,
          'subtotal' : Decimal
        }
        """
        products = Product.objects.filter(id__in=self.cart.keys())
        for p in products:
            qty = self.cart[str(p.id)]
            yield {
                "product": p,
                "qty": qty,
                "subtotal": qty * p.price,
            }

    def total(self):
        """Total de la compra (suma de subtotales)."""
        products = Product.objects.filter(id__in=self.cart.keys())
        return sum(p.price * self.cart[str(p.id)] for p in products)

    def count_items(self) -> int:
        """Número total de unidades (no de líneas)."""
        return sum(self.cart.values())
