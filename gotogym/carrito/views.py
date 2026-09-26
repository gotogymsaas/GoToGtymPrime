from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from gotogym.ratelimit import rate_limit
from inventory.services import get_available_quantity
from products.models import ProductVariant

from .services import build_cart_context, read_cart, write_cart

CARRITO_REINICIADO = (
    'Tu carrito se reinicio por una actualizacion del sistema. '
    'Vuelve a agregar los productos que quieras comprar.'
)


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _get_cart(request):
    cart, reiniciado = read_cart(request.session)
    if reiniciado:
        messages.warning(request, CARRITO_REINICIADO)
    return cart


def _responder(request, error=None, cart=None):
    if _is_ajax(request):
        if error:
            return JsonResponse({'success': False, 'error': error}, status=400)
        return JsonResponse({'success': True, 'cart_count': sum((cart or {}).values())})
    if error:
        messages.error(request, error)
    return redirect('carrito:cart_detail')


@login_required
@require_POST
@rate_limit('add_to_cart', limit=30, period_seconds=60)
def add_to_cart(request, variant_id):
    variante = get_object_or_404(ProductVariant, pk=variant_id, is_active=True)
    cart = _get_cart(request)

    en_carrito = int(cart.get(str(variante.id), 0))
    solicitado = en_carrito + 1
    disponible = get_available_quantity(variante)

    if solicitado > disponible:
        return _responder(
            request,
            error=f'Solo quedan {disponible} unidades de {variante.sku}.' if disponible
            else f'{variante.sku} no tiene unidades disponibles.',
        )

    cart[str(variante.id)] = solicitado
    write_cart(request.session, cart)
    return _responder(request, cart=cart)


@login_required
@require_POST
def remove_from_cart(request, variant_id):
    cart = _get_cart(request)
    cart.pop(str(variant_id), None)
    write_cart(request.session, cart)
    return _responder(request, cart=cart)


@login_required
@require_POST
def update_cart(request, variant_id):
    variante = get_object_or_404(ProductVariant, pk=variant_id, is_active=True)
    cart = _get_cart(request)

    try:
        cantidad = int(request.POST.get('cantidad', 1))
    except (TypeError, ValueError):
        return _responder(request, error='Cantidad invalida.')

    if cantidad <= 0:
        cart.pop(str(variante.id), None)
        write_cart(request.session, cart)
        return _responder(request, cart=cart)

    disponible = get_available_quantity(variante)
    if cantidad > disponible:
        return _responder(request, error=f'Solo quedan {disponible} unidades de {variante.sku}.')

    cart[str(variante.id)] = cantidad
    write_cart(request.session, cart)
    return _responder(request, cart=cart)


@login_required
def cart_detail(request):
    cart = _get_cart(request)
    return render(request, 'carrito/cart_detail.html', build_cart_context(cart))
