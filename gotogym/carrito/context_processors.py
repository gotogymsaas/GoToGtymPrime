from .services import CART_VERSION, SESSION_CART_KEY, SESSION_VERSION_KEY


def cart_count(request):
    """Unidades en el carrito, para el indicador del header.

    No usa `read_cart()` a proposito: esa funcion limpia la sesion cuando
    encuentra un carrito de una version anterior, y hacerlo aqui (en cada
    render de cada pagina) se tragaria el aviso de "tu carrito se reinicio"
    que la vista muestra al usuario. Aqui solo se lee: un carrito de otra
    version se informa como vacio y la vista se encarga de limpiarlo.
    """
    if request.session.get(SESSION_VERSION_KEY) != CART_VERSION:
        return {'cart_count': 0}
    cart = request.session.get(SESSION_CART_KEY) or {}
    return {'cart_count': sum(cart.values())}
