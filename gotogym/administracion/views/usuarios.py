"""Usuarios del panel (roles, estado, grupos) y roles intermedios (Grupos)."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..forms import GroupForm
from ..permissions import (
    grant_full_admin_permissions,
    require_perms,
    revoke_full_admin_permissions,
    staff_required,
)
from ._comun import _safe_redirect


@require_perms("accounts.view_user")
def users_list(request):
    User = get_user_model()
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    users = User.objects.order_by("-id")
    if query:
        users = users.filter(
            Q(email__icontains=query)
            | Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    if role == "admin":
        users = users.filter(is_staff=True)
    elif role == "afiliado":
        users = users.filter(is_staff=False, es_afiliado=True)
    elif role == "user":
        users = users.filter(is_staff=False, es_afiliado=False)
    elif role == "inactive":
        users = users.filter(is_active=False)
    paginator = Paginator(users, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "administracion/users.html",
        {
            "page_obj": page_obj,
            "query": query,
            "role": role,
            "all_groups": Group.objects.order_by("name"),
        },
    )


@require_perms("accounts.change_user")
@require_POST
def user_role_update(request, pk):
    """Cambia el rol (Usuario/Afiliado/Administrador) de un usuario.

    is_staff y es_afiliado son los flags ya existentes en el modelo; el
    rol es una combinacion de ambos, no un campo nuevo. Un admin no puede
    quitarse a si mismo el acceso administrativo desde aqui, para evitar
    quedar bloqueado fuera del panel sin otro administrador presente.
    """
    target = get_object_or_404(get_user_model(), pk=pk)
    nuevo_rol = request.POST.get("role", "")

    if target.pk == request.user.pk and nuevo_rol != "admin":
        messages.error(request, "No puedes quitarte a ti mismo el rol de administrador.")
        return _safe_redirect(request, "admin_users")

    if nuevo_rol == "admin":
        target.is_staff = True
        target.es_afiliado = False
    elif nuevo_rol == "afiliado":
        target.is_staff = False
        target.es_afiliado = True
    elif nuevo_rol == "user":
        target.is_staff = False
        target.es_afiliado = False
    else:
        messages.error(request, "Rol inválido.")
        return _safe_redirect(request, "admin_users")

    target.save(update_fields=["is_staff", "es_afiliado"])

    # El paquete completo de permisos es lo que hace que "Administrador"
    # tenga acceso a todo sin depender de un Grupo armado a mano; al bajar
    # de rol se retira ese paquete, pero sin tocar permisos que el usuario
    # tenga por pertenecer a un Grupo (un rol intermedio no depende de
    # haber sido Administrador antes).
    if nuevo_rol == "admin":
        grant_full_admin_permissions(target)
    else:
        revoke_full_admin_permissions(target)

    messages.success(request, f"Rol de {target.email} actualizado.")
    return _safe_redirect(request, "admin_users")


@require_perms("accounts.change_user")
@require_POST
def user_toggle_active(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
        return _safe_redirect(request, "admin_users")

    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    estado = "activada" if target.is_active else "desactivada"
    messages.success(request, f"Cuenta de {target.email} {estado}.")
    return _safe_redirect(request, "admin_users")


@require_perms("accounts.delete_user")
@require_POST
def user_delete(request, pk):
    target = get_object_or_404(get_user_model(), pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "No puedes eliminar tu propia cuenta.")
        return _safe_redirect(request, "admin_users")
    if target.is_superuser:
        messages.error(request, "No se puede eliminar una cuenta de superusuario desde el panel.")
        return _safe_redirect(request, "admin_users")

    email = target.email
    try:
        target.delete()
    except ProtectedError:
        # Comisiones, retiros y pagos son registros de dinero: no se borran en
        # cascada con la cuenta que los originó.
        messages.error(
            request,
            f"No se puede eliminar a {email}: tiene comisiones, retiros o pagos registrados. "
            "Desactiva la cuenta en lugar de eliminarla.",
        )
        return _safe_redirect(request, "admin_users")
    messages.success(request, f"Usuario {email} eliminado.")
    return _safe_redirect(request, "admin_users")


@require_perms("auth.add_group", "auth.change_group")
@require_POST
def user_groups_update(request, pk):
    """Asigna a un usuario los grupos (roles intermedios) marcados.

    Distinto de `user_role_update`: el rol basico (Usuario/Afiliado/
    Administrador) sigue viviendo en `is_staff`/`es_afiliado`, y esto
    es un permiso adicional, acotado, que solo tiene efecto si el usuario
    ya es staff (el panel completo sigue exigiendo `is_staff=True`; un
    Grupo nunca lo otorga por si solo).
    """
    target = get_object_or_404(get_user_model(), pk=pk)
    group_ids = request.POST.getlist("groups")
    target.groups.set(Group.objects.filter(pk__in=group_ids))
    messages.success(request, f"Grupos de {target.email} actualizados.")
    return _safe_redirect(request, "admin_users")


@staff_required
def groups_list(request):
    """Roles intermedios: Grupos de Django con un subconjunto de permisos
    del panel. Aparte de Usuario/Afiliado/Administrador, un Grupo permite
    darle a alguien acceso solo a, por ejemplo, inventario y cupones."""
    groups = Group.objects.order_by("name").prefetch_related("permissions")
    return render(request, "administracion/groups.html", {"groups": groups})


@require_perms("auth.add_group", "auth.change_group")
def group_edit(request, pk=None):
    group = get_object_or_404(Group, pk=pk) if pk else None
    if request.method == "POST":
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, "Grupo guardado.")
            return redirect("admin_groups")
    else:
        form = GroupForm(instance=group)
    return render(request, "administracion/group_form.html", {"form": form, "group": group})


@require_perms("auth.delete_group")
@require_POST
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group.delete()
    messages.success(request, "Grupo eliminado.")
    return redirect("admin_groups")
