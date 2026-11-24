"""Pantalla del panel con las tareas en segundo plano.

Es de solo lectura salvo el boton "Reintentar". No importa de `administracion`
(la capa de `tareas` esta por debajo): la proteccion se hace aqui, con los
permisos del propio modelo, y responde 403 a quien no los tiene.
"""
import logging
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import ejecucion
from .latido import LATIDO_MAXIMO_SEGUNDOS, edad_del_latido, trabajador_habilitado
from .models import EstadoTarea, TareaPendiente, TareaPeriodica

logger = logging.getLogger(__name__)

LIMITE_FILAS = 100


def _requiere_permiso(permiso):
    def decorador(vista):
        @never_cache
        @login_required
        @wraps(vista)
        def envuelta(request, *args, **kwargs):
            if not (request.user.is_staff and request.user.has_perm(permiso)):
                raise PermissionDenied
            return vista(request, *args, **kwargs)
        return envuelta
    return decorador


@_requiere_permiso('tareas.view_tareapendiente')
def lista(request):
    fallidas = TareaPendiente.objects.filter(estado=EstadoTarea.FALLIDA).order_by('-terminada', '-pk')
    pendientes = TareaPendiente.objects.filter(
        estado__in=[EstadoTarea.PENDIENTE, EstadoTarea.EN_CURSO],
    ).order_by('proximo_intento', 'pk')
    edad = edad_del_latido()
    return render(request, 'tareas/lista.html', {
        'fallidas': fallidas[:LIMITE_FILAS],
        'total_fallidas': fallidas.count(),
        'pendientes': pendientes[:LIMITE_FILAS],
        'total_pendientes': pendientes.count(),
        'periodicas': TareaPeriodica.objects.order_by('nombre'),
        'habilitado': trabajador_habilitado(),
        'latido_edad': edad,
        'latido_caido': trabajador_habilitado() and (edad is None or edad > LATIDO_MAXIMO_SEGUNDOS),
        'puede_reintentar': request.user.has_perm('tareas.retry_tarea'),
    })


@require_POST
@_requiere_permiso('tareas.retry_tarea')
def reintentar(request, pk):
    tarea = get_object_or_404(TareaPendiente, pk=pk)
    if ejecucion.reintentar(tarea.pk):
        logger.info('La tarea %s (%s) se devolvió a la cola desde el panel (usuario %s).',
                    tarea.pk, tarea.ruta, request.user.pk)
        messages.success(request, _('La tarea volvió a la cola. El trabajador la ejecutará en breve.'))
    else:
        messages.error(request, _('Solo se pueden reintentar las tareas fallidas.'))
    return redirect('admin_tareas')
