import mercadopago
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from products.models import Product
from django.shortcuts import render, redirect
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required(login_url='/accounts/login/')
def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "El carrito está vacío. Agrega productos antes de pagar.")
        return redirect('carrito:cart_detail')
    productos = Product.objects.filter(id__in=cart.keys())
    preference_items = []
    for producto in productos:
        cantidad = cart[str(producto.id)]
        if cantidad > 0:
            # Calcular precio con descuento si aplica
            price = float(producto.price)
            if producto.discount:
                price = float(producto.price) * (1 - producto.discount / 100)
            preference_items.append({
                "title": producto.name,
                "quantity": int(cantidad),
                "unit_price": round(price, 2),
                "currency_id": "COP"
            })
    if not preference_items:
        messages.error(request, "No hay productos válidos para pagar.")
        return redirect('carrito:cart_detail')
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    preference_data = {
        "items": preference_items,
        "back_urls": {
            "success": request.build_absolute_uri(reverse('carrito:payment_status')),
            "failure": request.build_absolute_uri(reverse('carrito:payment_status')),
            "pending": request.build_absolute_uri(reverse('carrito:payment_status')),
        },
        "auto_return": "approved",
    }
    preference_response = sdk.preference().create(preference_data)
    preference = preference_response.get("response", {})
    # Log para depuración
    print('MercadoPago response:', preference_response)
    init_point = preference.get("init_point")
    if not init_point:
        error_message = preference.get('message', 'No se pudo iniciar el pago con MercadoPago. Intenta más tarde.')
        # Mostrar detalles del error si existen
        if 'cause' in preference:
            error_message += ' ' + str(preference['cause'])
        messages.error(request, error_message)
        return redirect('carrito:cart_detail')
    return redirect(init_point)

@login_required(login_url='/accounts/login/')
def payment_status(request):
    status = request.GET.get('collection_status')
    payment_id = request.GET.get('payment_id')
    merchant_order_id = request.GET.get('merchant_order_id')
    if status == 'approved':
        request.session['cart'] = {}
    context = {
        'status': status,
        'payment_id': payment_id,
        'merchant_order_id': merchant_order_id,
    }
    return render(request, 'carrito/payment_status.html', context)
