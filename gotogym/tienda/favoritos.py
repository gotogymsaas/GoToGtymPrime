"""Lista de favoritos del cliente: lectura para las plantillas y escritura.

Las tarjetas y la galeria preguntan "es favorito?" producto por producto.
Para no hacer una consulta por tarjeta, cada vista pide una sola vez el
conjunto de ids (`ids_favoritos`) y lo pasa al contexto como
`favoritos_ids`; el partial del corazon solo comprueba pertenencia.
"""
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from products.models import ProductFavorite, ProductMedia

from .catalog import (
    ORDEN_DEL_PANEL,
    build_product_card,
    catalog_variants_queryset,
    curated_product_cards,
    storefront_products,
)

MAX_RELACIONADOS = 12


def ids_favoritos(user):
    """Ids de los productos que la persona tiene en favoritos (vacio si no
    ha iniciado sesion)."""
    if not getattr(user, 'is_authenticated', False):
        return frozenset()
    return frozenset(
        ProductFavorite.objects.filter(user=user).values_list('product_id', flat=True)
    )


def _con_tarjeta(queryset):
    return queryset.select_related('category', 'brand').prefetch_related(
        Prefetch('variants', queryset=catalog_variants_queryset()),
        Prefetch('media', queryset=ProductMedia.objects.order_by('-is_primary', 'sort_order', 'id')),
    )


def tarjetas_favoritas(user):
    """Tarjetas de los favoritos que la tienda todavia puede vender, del mas
    reciente al mas antiguo.

    Un producto cuyas variantes se desactivaron todas sale del catalogo; el
    favorito no se borra (si vuelve a venderse reaparece), pero mientras
    tanto no se muestra una tarjeta que lleva a una ficha 404.
    """
    if not getattr(user, 'is_authenticated', False):
        return []
    productos = _con_tarjeta(
        storefront_products().filter(favorites__user=user)
    ).order_by('-favorites__created_at', *ORDEN_DEL_PANEL)
    return [build_product_card(producto) for producto in productos]


def tarjetas_relacionadas(favoritos_cards, limite=MAX_RELACIONADOS):
    """Recomendaciones para debajo de la lista de favoritos.

    Relacionado es lo mismo que en la ficha de producto: la misma categoria.
    Aqui se toman las categorias de todos los favoritos, sin repetir los
    que ya estan guardados y solo con unidades para vender (recomendar algo
    agotado no lleva a ninguna compra). Destacados primero y luego el orden
    del panel.

    Sin favoritos (o si sus categorias no tienen nada mas que ofrecer) se
    usa la seleccion curada de la tienda, para que la seccion no quede vacia.
    """
    favoritos = [card['product'] for card in favoritos_cards]
    excluir = {producto.pk for producto in favoritos}
    categorias = {producto.category_id for producto in favoritos}
    if categorias:
        productos = list(
            _con_tarjeta(
                storefront_products()
                .filter(
                    category_id__in=categorias,
                    variants__is_active=True,
                    variants__inventory__quantity_available__gt=0,
                )
                .exclude(pk__in=excluir)
                .distinct()
            ).order_by('-featured', *ORDEN_DEL_PANEL)[:limite]
        )
        if productos:
            return [build_product_card(producto) for producto in productos]
    # Se piden de mas porque se descartan los que ya son favoritos.
    curados = curated_product_cards(limit=limite + len(excluir))
    return [card for card in curados if card['product'].pk not in excluir][:limite]


def fijar_favorito(user, product, favorito):
    """Deja el producto dentro (`favorito=True`) o fuera de favoritos.

    Recibe el estado deseado y no "alterna": el boton envia lo que la persona
    vio al hacer clic, asi que un doble clic o una pestana desactualizada no
    terminan en el estado contrario. Es idempotente, y dos peticiones
    simultaneas no duplican la fila: la restriccion unica del modelo rechaza
    la segunda y se trata como "ya estaba".
    """
    if not favorito:
        ProductFavorite.objects.filter(user=user, product=product).delete()
        return False
    try:
        with transaction.atomic():
            ProductFavorite.objects.get_or_create(user=user, product=product)
    except IntegrityError:
        pass
    return True
