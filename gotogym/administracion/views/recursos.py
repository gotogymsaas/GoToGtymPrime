"""Recursos de marca para afiliados."""

from afiliados.models import RecursoMarca
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..forms import RecursoMarcaForm
from ..permissions import (
    require_perms,
    staff_required,
)


@staff_required
def recursos_list(request):
    return render(request, "administracion/recursos.html", {"recursos": RecursoMarca.objects.all()})


@require_perms("afiliados.add_recursomarca", "afiliados.change_recursomarca")
def recurso_edit(request, pk=None):
    recurso = get_object_or_404(RecursoMarca, pk=pk) if pk else None
    if request.method == "POST":
        form = RecursoMarcaForm(request.POST, request.FILES, instance=recurso)
        if form.is_valid():
            form.save()
            messages.success(request, "Recurso guardado.")
            return redirect("admin_recursos")
    else:
        form = RecursoMarcaForm(instance=recurso)
    return render(request, "administracion/recurso_form.html", {"form": form, "recurso": recurso})


@require_perms("afiliados.delete_recursomarca")
@require_POST
def recurso_delete(request, pk):
    recurso = get_object_or_404(RecursoMarca, pk=pk)
    recurso.file.delete(save=False)
    recurso.delete()
    messages.success(request, "Recurso eliminado.")
    return redirect("admin_recursos")
