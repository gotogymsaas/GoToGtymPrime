from django.shortcuts import render, redirect, get_object_or_404
from .models import ColorMarca
from .forms import ColorMarcaForm
from django.views.decorators.csrf import csrf_exempt


def paleta(request):
    colores = ColorMarca.objects.all()
    color_navbar = None
    if colores.count() >= 10:
        color_navbar = colores[9].codigo_hex
    if request.method == 'POST':
        for color in colores:
            nombre = request.POST.get(f'nombre_{color.pk}')
            codigo_hex = request.POST.get(f'codigo_hex_{color.pk}')
            if nombre and codigo_hex:
                color.nombre = nombre
                color.codigo_hex = codigo_hex
                color.save()
        return redirect('configuracion_marca:paleta')
    return render(request, 'configuracion_marca/paleta.html', {'colores': colores, 'color_navbar': color_navbar})


def editar_color(request, pk):
    color = get_object_or_404(ColorMarca, pk=pk)
    if request.method == 'POST':
        form = ColorMarcaForm(request.POST, instance=color)
        if form.is_valid():
            form.save()
            return redirect('configuracion_marca:paleta')
    else:
        form = ColorMarcaForm(instance=color)
    return render(request, 'configuracion_marca/editar_color.html', {'form': form, 'color': color})
