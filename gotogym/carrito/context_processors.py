def cart_count(request):
    cart = request.session.get('cart', {})
    num_items = sum(cart.values())
    return {'cart_count': num_items}
