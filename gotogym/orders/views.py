from decimal import Decimal

from carrito.services import build_cart_context, read_cart, write_cart
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from products.forms import ProductReviewForm
from shipping.services import get_mock_quote
from tienda.catalog import curated_product_cards

from .colombia_data import MUNICIPIOS_POR_DEPARTAMENTO
from .forms import CheckoutForm
from .models import Order, OrderItem, OrderStatus
from .services import CheckoutError, create_order_from_cart, get_usable_coupon

REVIEWABLE_ORDER_STATUSES = {
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARING,
    OrderStatus.SHIPPED,
    OrderStatus.IN_TRANSIT,
    OrderStatus.DELIVERED,
}


@login_required
def checkout(request):
    cart, reiniciado = read_cart(request.session)
    if reiniciado:
        messages.warning(request, 'Tu carrito se reinicio por una actualizacion del sistema.')

    resumen = build_cart_context(cart)
    if not resumen['items']:
        messages.info(request, 'Tu carrito esta vacio.')
        return redirect('carrito:cart_detail')

    # float, no Decimal: es lo que necesita json_script para que el JS de
    # la cotizacion de envio pueda sumarlo sin parsearlo (mismo patron que
    # variantes_json en tienda/views.py).
    resumen['subtotal_float'] = float(resumen['subtotal'])
    resumen['coupon_discount'] = 0

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                pedido = create_order_from_cart(request.user, cart, form.cleaned_data)
            except CheckoutError as error:
                messages.error(request, str(error))
            else:
                # El carrito solo se vacia si el pedido quedo creado.
                write_cart(request.session, {})
                return redirect('payments:pending', order_number=pedido.order_number)
    else:
        form = CheckoutForm(initial={
            'email': request.user.email,
            'first_name': request.user.first_name or '',
            'last_name': request.user.last_name or '',
        })

    return render(request, 'orders/checkout.html', {
        'form': form,
        'resumen': resumen,
        'municipios_por_departamento': MUNICIPIOS_POR_DEPARTAMENTO,
    })


@login_required
def cotizar_envio(request):
    """Cotizacion en vivo para el resumen del checkout, antes de confirmar.

    Usa exactamente el mismo calculo que create_order_from_cart (mismo
    subtotal, mismo motor de tarifas): el numero que ve el comprador aqui
    tiene que ser el mismo que se cobra al confirmar, o el resumen estaria
    mostrando una promesa que despues no cumple.

    El subtotal sale siempre del carrito en sesion, nunca de un parametro
    del cliente: si se aceptara un subtotal por GET, cualquiera podria
    pedir la tarifa de envio gratis mandando un monto inventado.
    """
    ciudad = (request.GET.get('city') or '').strip()
    if not ciudad:
        return JsonResponse({'error': 'Falta la ciudad.'}, status=400)

    cart, _reiniciado = read_cart(request.session)
    resumen = build_cart_context(cart)
    if not resumen['items']:
        return JsonResponse({'error': 'El carrito esta vacio.'}, status=400)

    subtotal = Decimal(resumen['subtotal']).quantize(Decimal('0.01'))
    cotizacion = get_mock_quote(ciudad, subtotal)
    envio = Decimal(cotizacion['cost']).quantize(Decimal('0.01'))

    return JsonResponse({
        'cost': float(envio),
        'is_free': envio == 0,
        'estimated_days': cotizacion['estimated_days'],
        'method_name': cotizacion['method_name'],
        'subtotal': float(subtotal),
        'total': float(subtotal + envio),
    })


@login_required
def validar_cupon(request):
    """Vista previa en vivo del descuento de un cupon, antes de confirmar.

    Igual que `cotizar_envio`: el subtotal sale del carrito en sesion, nunca
    de un parametro del cliente, para que la vista previa no pueda inflarse
    con un monto inventado. El descuento real que se cobra siempre se
    recalcula de nuevo en `create_order_from_cart`.
    """
    codigo = (request.GET.get('code') or '').strip()
    cart, _reiniciado = read_cart(request.session)
    resumen = build_cart_context(cart)
    if not resumen['items']:
        return JsonResponse({'error': 'El carrito esta vacio.'}, status=400)

    subtotal = Decimal(resumen['subtotal']).quantize(Decimal('0.01'))
    cupon = get_usable_coupon(codigo)
    if cupon is None:
        return JsonResponse({'valid': False})

    descuento = cupon.compute_discount(subtotal)
    return JsonResponse({
        'valid': True,
        'code': cupon.code,
        'discount': float(descuento),
        'discount_type': cupon.discount_type,
        'value': float(cupon.value),
    })


@login_required
def my_orders(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .select_related('address')
        .order_by('-created_at')
    )
    return render(request, 'orders/my_orders.html', {
        'orders': orders,
        'recommended_cards': [] if orders.exists() else curated_product_cards(limit=3),
    })


@login_required
def order_detail(request, order_number):
    pedido = get_object_or_404(
        Order.objects.prefetch_related('items__review').select_related('address', 'shipping_quote'),
        order_number=order_number,
        user=request.user,
    )
    return render(request, 'orders/order_detail.html', {
        'pedido': pedido,
        'puede_resenar': pedido.order_status in REVIEWABLE_ORDER_STATUSES,
    })


@login_required
def create_review(request, order_number, item_id):
    pedido = get_object_or_404(Order, order_number=order_number, user=request.user)
    item = get_object_or_404(
        OrderItem.objects.select_related('variant__product'), id=item_id, order=pedido,
    )
    if pedido.order_status not in REVIEWABLE_ORDER_STATUSES or not item.variant_id:
        messages.error(request, 'Solo puedes calificar productos de pedidos confirmados.')
        return redirect('orders:order_detail', order_number=pedido.order_number)
    if hasattr(item, 'review'):
        messages.info(request, 'Ya calificaste este producto.')
        return redirect('orders:order_detail', order_number=pedido.order_number)

    if request.method != 'POST':
        return redirect('orders:order_detail', order_number=pedido.order_number)

    form = ProductReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = item.variant.product
        review.order_item = item
        review.user = request.user
        review.save()
        messages.success(request, 'Gracias por compartir tu opinión.')
    else:
        messages.error(request, 'Revisa la calificación e inténtalo de nuevo.')
    return redirect('orders:order_detail', order_number=pedido.order_number)
