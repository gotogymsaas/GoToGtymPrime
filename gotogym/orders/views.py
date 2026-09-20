from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from carrito.services import build_cart_context, read_cart, write_cart

from .colombia_data import MUNICIPIOS_POR_DEPARTAMENTO
from .forms import CheckoutForm
from .models import Order
from .services import CheckoutError, create_order_from_cart


@login_required
def checkout(request):
    cart, reiniciado = read_cart(request.session)
    if reiniciado:
        messages.warning(request, 'Tu carrito se reinicio por una actualizacion del sistema.')

    resumen = build_cart_context(cart)
    if not resumen['items']:
        messages.info(request, 'Tu carrito esta vacio.')
        return redirect('carrito:cart_detail')

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
def my_orders(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .select_related('address')
        .order_by('-created_at')
    )
    return render(request, 'orders/my_orders.html', {'orders': orders})


@login_required
def order_detail(request, order_number):
    pedido = get_object_or_404(
        Order.objects.prefetch_related('items').select_related('address', 'shipping_quote'),
        order_number=order_number,
        user=request.user,
    )
    return render(request, 'orders/order_detail.html', {'pedido': pedido})
