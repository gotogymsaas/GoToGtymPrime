import mercadopago
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from products.models import Product
from django.shortcuts import render, redirect
from decimal import Decimal
from django.contrib.auth.decorators import login_required

@login_required(login_url='/accounts/login/')
def checkout(request):
    cart = request.session.get('cart', {})
    productos = Product.objects.filter(id__in=cart.keys())
    preference_items = []
    for producto in productos:
        cantidad = cart[str(producto.id)]
        preference_items.append({
            "title": producto.name,
            "quantity": int(cantidad),
            "unit_price": float(producto.price),
            "currency_id": "COP"
        })
    
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    preference_data = {
        "items": preference_items,
        "back_urls": {
            "success": request.build_absolute_uri(reverse('carrito:cart_detail')),
            "failure": request.build_absolute_uri(reverse('carrito:cart_detail')),
            "pending": request.build_absolute_uri(reverse('carrito:cart_detail')),
        },
        "auto_return": "approved",
    }
    preference_response = sdk.preference().create(preference_data)
    preference = preference_response["response"]
    init_point = preference["init_point"]
    return redirect(init_point)
