from django.shortcuts import render, redirect, get_object_or_404
from .models import ProductCategory, Product, Brand
from django import forms
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .forms import ProductForm

class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ['name', 'description']

def add_category(request):
    if request.method == 'POST':
        form = ProductCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('products:list_category')
    else:
        form = ProductCategoryForm()
    return render(request, 'products/add_category.html', {'form': form})

def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('products:list_product')
    else:
        form = ProductForm()
    return render(request, 'products/add_product.html', {'form': form})

def list_category(request):
    categories = ProductCategory.objects.all()
    paginator = Paginator(categories, 4)  # 4 categorías por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'products/list_category.html', {'categories': page_obj, 'page_obj': page_obj})

def list_product(request):
    products = Product.objects.select_related('category').all()
    paginator = Paginator(products, 4)  # 4 productos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'products/list_product.html', {'products': page_obj, 'page_obj': page_obj})

def view_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'products/view_product.html', {'product': product})

def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            # Si el usuario eliminó la imagen desde el frontend
            if request.POST.get('image-clear') == '1':
                if product.image:
                    product.image.delete(save=False)
                product.image = None
            # Si sube una nueva imagen, se actualiza automáticamente
            form.save()
            return redirect('products:list_product')
    else:
        form = ProductForm(instance=product)
    return render(request, 'products/edit_product.html', {'form': form, 'edit': True, 'product': product})

def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        return redirect('products:list_product')
    return render(request, 'products/delete_product.html', {'product': product})

@csrf_exempt
def delete_product_image(request, pk):
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)
        if product.image:
            product.image.delete(save=False)
            product.image = None
            product.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

def edit_category(request, pk):
    category = get_object_or_404(ProductCategory, pk=pk)
    if request.method == 'POST':
        form = ProductCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect('products:list_category')
    else:
        form = ProductCategoryForm(instance=category)
    return render(request, 'products/edit_category.html', {'form': form, 'category': category})

def delete_category(request, pk):
    category = get_object_or_404(ProductCategory, pk=pk)
    if request.method == 'POST':
        category.delete()
        return redirect('products:list_category')
    return render(request, 'products/delete_category.html', {'category': category})

@csrf_exempt
def delete_category_ajax(request, pk):
    if request.method == 'POST':
        category = get_object_or_404(ProductCategory, pk=pk)
        category.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

def view_category(request, pk):
    category = get_object_or_404(ProductCategory, pk=pk)
    return render(request, 'products/view_category.html', {'category': category})

# Listar y añadir marca
def brand_list(request):
    marcas = Brand.objects.all().order_by('name')
    marca = None
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            Brand.objects.create(name=name)
            return redirect('products:brand_list')
    return render(request, 'products/brand_list.html', {'marcas': marcas, 'marca': marca})

# Editar marca
def brand_edit(request, pk):
    marca = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            marca.name = name
            marca.save()
            return redirect('products:brand_list')
    marcas = Brand.objects.all().order_by('name')
    return render(request, 'products/brand_list.html', {'marcas': marcas, 'marca': marca})

# Previsualizar marca
def brand_preview(request, pk):
    marca = get_object_or_404(Brand, pk=pk)
    return render(request, 'products/brand_preview.html', {'marca': marca})

# Eliminar marca
@require_POST
def brand_delete(request, pk):
    marca = get_object_or_404(Brand, pk=pk)
    marca.delete()
    return redirect('products:brand_list')
