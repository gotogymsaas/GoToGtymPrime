# cart/views.py
from django.shortcuts import redirect, render, get_object_or_404
from django.views import View
from products.models import Product
from .cart import SessionCart
from integrations.mercadopago.mercadopago_client import MercadoPagoClient


class AddToCart(View):
    """
    ▸ Añade qty unidades (o las suma si ya existe).
    """
    def post(self, request, pk):
        qty = int(request.POST.get("qty", 1))
        SessionCart(request).add(pk, qty)
        return redirect("cart:detail")


class RemoveFromCart(View):
    """
    ▸ Elimina por completo un producto del carrito.
    """
    def post(self, request, pk):
        SessionCart(request).remove(pk)
        return redirect("cart:detail")


class UpdateCart(View):
    """
    ▸ Actualiza la cantidad de un producto.
      – action=inc ➜ +1  
      – action=dec ➜ –1 (y lo quita si llega a 0)  
      – qty=<número> ➜ fija la cantidad exactamente
    """
    def post(self, request, pk):
        cart = SessionCart(request)

        action = request.POST.get("action")
        if action == "inc":
            cart.add(pk, 1)               # suma una unidad
        elif action == "dec":
            cart.add(pk, -1)              # resta una unidad (cart se encarga de borrar si llega a 0)
        else:
            # qty enviada manualmente
            try:
                qty = int(request.POST.get("qty", 1))
            except (TypeError, ValueError):
                qty = 1
            cart.set(pk, qty)             # método “set” que fijará la cantidad (implémentalo en SessionCart)

        return redirect("cart:detail")


class CartDetail(View):
    """
    ▸ Muestra el contenido del carrito.
    """
    template_name = "cart/detail.html"

    def get(self, request):
        cart = SessionCart(request)
        return render(request, self.template_name, {"cart": cart})


class CheckoutView(View):
    """Create a Mercado Pago preference for the current cart."""

    def post(self, request):
        cart = SessionCart(request)
        products = Product.objects.filter(id__in=cart.cart.keys())

        items = []
        for p in products:
            qty = cart.cart[str(p.id)]
            items.append({
                "title": p.name,
                "quantity": int(qty),
                "unit_price": float(p.price),
                "currency_id": "USD",
            })

        if not items:
            return redirect("cart:detail")

        preference_data = {"items": items}
        client = MercadoPagoClient()
        response = client.create_preference(preference_data)
        init_point = response.get("init_point")
        if init_point:
            return redirect(init_point)
        return redirect("cart:detail")
