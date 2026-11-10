"""Bandeja de solicitudes de atencion humana (radicados)."""
from atencion.models import SolicitudAtencion
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .permissions import staff_required


@staff_required
def atencion_list(request):
    estado = request.GET.get("estado", "").strip()
    query = request.GET.get("q", "").strip()
    solicitudes = SolicitudAtencion.objects.all()
    if estado in SolicitudAtencion.Estado.values:
        solicitudes = solicitudes.filter(estado=estado)
    if query:
        solicitudes = solicitudes.filter(radicado__icontains=query) | solicitudes.filter(email__icontains=query)
    page_obj = Paginator(solicitudes, 20).get_page(request.GET.get("page"))
    return render(request, "administracion/atencion.html", {
        "page_obj": page_obj, "estado": estado, "query": query,
        "estados": SolicitudAtencion.Estado.choices,
        "abiertas": SolicitudAtencion.objects.filter(estado=SolicitudAtencion.Estado.ABIERTA).count(),
    })


@staff_required
def atencion_detail(request, pk):
    solicitud = get_object_or_404(SolicitudAtencion, pk=pk)
    return render(request, "administracion/atencion_detail.html", {
        "solicitud": solicitud, "estados": SolicitudAtencion.Estado.choices,
    })


@staff_required
@require_POST
def atencion_update_estado(request, pk):
    solicitud = get_object_or_404(SolicitudAtencion, pk=pk)
    estado = request.POST.get("estado", "")
    if estado not in SolicitudAtencion.Estado.values:
        messages.error(request, "Estado no válido.")
    elif estado != solicitud.estado:
        solicitud.estado = estado
        solicitud.save(update_fields=["estado", "actualizada"])
        messages.success(request, f"{solicitud.radicado}: {solicitud.get_estado_display()}.")
    return redirect("admin_atencion_detail", pk=solicitud.pk)
