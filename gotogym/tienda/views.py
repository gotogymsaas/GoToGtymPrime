from django.shortcuts import render, get_object_or_404
from products.models import Product, ProductCategory, Brand
from django.core.paginator import Paginator
from django.db.models import F

def producto_list(request):
    productos = Product.objects.all()
    categorias = ProductCategory.objects.all()
    marcas = Brand.objects.all()
    filtro = request.GET.get('filtro', '')
    categoria_id = request.GET.get('categoria')
    precio_min = request.GET.get('precio_min')
    precio_max = request.GET.get('precio_max')
    rating = request.GET.get('rating')
    orden = request.GET.get('orden')

    if filtro:
        productos = productos.filter(name__icontains=filtro)
    if categoria_id:
        productos = productos.filter(category_id=categoria_id)
    if precio_min:
        productos = productos.filter(price__gte=precio_min)
    if precio_max:
        productos = productos.filter(price__lte=precio_max)
    if rating:
        try:
            rating_value = float(rating)
            productos = productos.filter(rating__gte=rating_value)
        except Exception:
            pass
    if orden == 'precio_asc':
        productos = productos.order_by('price')
    elif orden == 'precio_desc':
        productos = productos.order_by('-price')
    elif orden == 'nombre_asc':
        productos = productos.order_by('name')
    elif orden == 'nombre_desc':
        productos = productos.order_by('-name')

    paginator = Paginator(productos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    featured_products = Product.objects.filter(featured=True)

    context = {
        'productos': page_obj,
        'categorias': categorias,
        'marcas': marcas,
        'filtro': filtro,
        'page_obj': page_obj,
        'featured_products': featured_products,
    }
    return render(request, 'tienda/producto_list.html', context)

def producto_detail(request, pk):
    producto = get_object_or_404(Product, pk=pk)
    # Obtener 4 productos relacionados de la misma categoría, excluyendo el actual
    related_products = Product.objects.filter(category=producto.category).exclude(pk=producto.pk)[:4]
    context = {
        'producto': producto,
        'related_products': related_products,
    }
    return render(request, 'tienda/producto_detail.html', context)
