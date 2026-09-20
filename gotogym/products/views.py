"""CRUD heredado, deprecado en favor del panel `administracion`.

Este modulo duplicaba exactamente lo que ya hace `administracion` (crear,
editar y eliminar productos/categorias/marcas), y mantener dos formularios
divergentes del mismo dominio es justo el riesgo que se queria evitar. Las
vistas de HTML redirigen a su equivalente en el panel; las dos de AJAX
devuelven 410 (Gone) en vez de ejecutar la mutacion.

Se conservan como redirects, en vez de borrarse, para no romper enlaces o
marcadores existentes hacia estas URLs.
"""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache

_MENSAJE_AJAX_DEPRECADO = {
    'success': False,
    'error': 'Este endpoint fue reemplazado por el panel de administracion.',
}


def staff_required(view_func):
    decorated = never_cache(login_required(user_passes_test(lambda user: user.is_staff)(view_func)))
    return decorated


@staff_required
def add_category(request):
    return redirect('admin_catalogs')


@staff_required
def add_product(request):
    return redirect('admin_product_new')


@staff_required
def list_category(request):
    return redirect('admin_catalogs')


@staff_required
def list_product(request):
    return redirect('admin_products')


@staff_required
def view_product(request, pk):
    return redirect('admin_product_edit', pk=pk)


@staff_required
def edit_product(request, pk):
    return redirect('admin_product_edit', pk=pk)


@staff_required
def delete_product(request, pk):
    return redirect('admin_product_edit', pk=pk)


@staff_required
def delete_product_image(request, pk):
    return JsonResponse(_MENSAJE_AJAX_DEPRECADO, status=410)


@staff_required
def edit_category(request, pk):
    return redirect('admin_catalogs')


@staff_required
def delete_category(request, pk):
    return redirect('admin_catalogs')


@staff_required
def delete_category_ajax(request, pk):
    return JsonResponse(_MENSAJE_AJAX_DEPRECADO, status=410)


@staff_required
def view_category(request, pk):
    return redirect('admin_catalogs')


@staff_required
def brand_list(request):
    return redirect('admin_catalogs')


@staff_required
def brand_edit(request, pk):
    return redirect('admin_catalogs')


@staff_required
def brand_preview(request, pk):
    return redirect('admin_catalogs')


@staff_required
def brand_delete(request, pk):
    return redirect('admin_catalogs')
