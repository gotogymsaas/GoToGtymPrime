from .cart import SessionCart


def cart_counter(request):
    cart = SessionCart(request)
    return {"cart_items_count": cart.count_items()}
