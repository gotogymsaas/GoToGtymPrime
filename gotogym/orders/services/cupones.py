"""Busqueda y uso de cupones de descuento."""
from django.db.models import F

from ..models import Coupon


def get_usable_coupon(coupon_code, user=None):
    """Busca un cupon utilizable por su codigo, o None si no aplica.

    Centraliza la busqueda para que el formulario (validacion) y el
    servicio de creacion del pedido (aplicacion real) usen exactamente el
    mismo criterio de "utilizable". Si `user` es el propio afiliado dueño
    del cupon, se trata como no utilizable (autorreferencia): nadie debe
    autoaplicarse el descuento ni generar comision sobre su propia compra.
    """
    codigo = (coupon_code or '').strip().upper()
    if not codigo:
        return None
    cupon = Coupon.objects.filter(code=codigo).select_related('afiliado').first()
    if cupon is None or not cupon.is_usable():
        return None
    # Un afiliado cuyo preaviso de baja ya vencio deja de aceptarse aunque la
    # baja todavia no se haya aplicado en la base.
    if cupon.afiliado_id and not cupon.afiliado.es_operativo():  # type: ignore[union-attr]
        return None
    autenticado = user is not None and getattr(user, 'is_authenticated', False)
    if cupon.afiliado_id and autenticado and cupon.afiliado.user_id == user.id:  # type: ignore[union-attr]
        return None
    if cupon.customer_segment_id:
        # Cupon restringido a un segmento de cliente (p. ej. entrenadores,
        # clubes): sin sesion o fuera del segmento, se trata como no
        # utilizable, igual que un cupon vencido.
        if not autenticado or not user.customer_segments.filter(pk=cupon.customer_segment_id).exists():
            return None
    return cupon


def es_cupon_propio(coupon_code, user):
    """Si el codigo es el cupon personal del afiliado que esta comprando.

    `get_usable_coupon` lo rechaza igual que a uno inexistente; esto permite
    decirle a la persona por que, en vez de un "no valido" que la hace creer
    que su codigo esta roto."""
    codigo = (coupon_code or '').strip().upper()
    if not codigo or user is None or not getattr(user, 'is_authenticated', False):
        return False
    return Coupon.objects.filter(code=codigo, afiliado__user=user).exists()


def release_coupon(order):
    """Devuelve el uso del cupon de un pedido que no se concreto.

    Se llama una sola vez, al pasar el pedido a `cancelled` (un estado final:
    no se vuelve a salir de el). Sin esto, los pedidos abandonados o con el
    pago rechazado agotarian los cupones de uso limitado."""
    if order.coupon_id:
        Coupon.objects.filter(pk=order.coupon_id, times_used__gt=0).update(times_used=F('times_used') - 1)
