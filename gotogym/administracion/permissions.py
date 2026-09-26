"""Permisos granulares del panel admin.

No se inventa un sistema de permisos propio: se reutilizan los permisos
que Django ya crea automaticamente para cada modelo (`add_x`, `change_x`,
`delete_x`, `view_x`). Esta lista es el catalogo de esos permisos que
tienen sentido dentro del panel; sirve para tres cosas:

1. Decidir que permiso exige cada vista sensible (`require_perms`).
2. Ofrecer un catalogo acotado al crear un Grupo (rol intermedio) en
   "Configuracion > Grupos y permisos", en vez de mostrar los cientos de
   permisos que trae Django por defecto.
3. Definir el paquete completo que un usuario recibe al ser ascendido al
   rol "Administrador" (ver `grant_full_admin_permissions`).

Anadir un permiso nuevo en el futuro (por ejemplo para un modulo nuevo del
panel) es agregar una tupla aqui y decorar la vista correspondiente con
`require_perms`; no hace falta tocar el esquema de nuevo.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache

ADMIN_PERM_SPECS = [
    ('products', 'add_product'),
    ('products', 'change_product'),
    ('products', 'delete_product'),
    ('products', 'add_producttag'),
    ('products', 'change_producttag'),
    ('products', 'delete_producttag'),
    ('products', 'add_productcategory'),
    ('products', 'delete_productcategory'),
    ('products', 'add_brand'),
    ('products', 'delete_brand'),
    ('inventory', 'change_inventory'),
    ('orders', 'add_coupon'),
    ('orders', 'change_coupon'),
    ('orders', 'delete_coupon'),
    ('accounts', 'change_user'),
    ('accounts', 'delete_user'),
    ('auth', 'add_group'),
    ('auth', 'change_group'),
    ('auth', 'delete_group'),
    ('administracion', 'change_panelsettings'),
]

ADMIN_PERM_CODENAMES = [f'{app_label}.{codename}' for app_label, codename in ADMIN_PERM_SPECS]


def admin_permission_queryset():
    from django.contrib.auth.models import Permission
    from django.db.models import Q

    query = Q()
    for app_label, codename in ADMIN_PERM_SPECS:
        query |= Q(content_type__app_label=app_label, codename=codename)
    return Permission.objects.filter(query)


def grant_full_admin_permissions(user):
    """Le da a `user` el paquete completo de permisos del panel.

    Es lo que distingue al rol "Administrador" de un rol intermedio hecho
    a mano con un Grupo: Administrador siempre tiene acceso a todo, sin
    depender de que alguien le haya armado el grupo correcto.
    """
    user.user_permissions.add(*admin_permission_queryset())


def revoke_full_admin_permissions(user):
    """Quita el paquete de permisos de panel asignado directamente al
    usuario. No toca los permisos que el usuario tenga por pertenecer a un
    Grupo: un rol intermedio no depende de haber sido "Administrador"
    antes."""
    user.user_permissions.remove(*admin_permission_queryset())


def _self_heal_legacy_admin(user):
    """Si una cuenta ya era `is_staff=True` antes de este sistema de
    permisos granulares (creada a mano, por una migracion vieja, o en
    otra base de datos), le completa el paquete de permisos la primera
    vez que hace cualquier peticion al panel. Evita depender de una
    migracion de datos que tendria que adivinar en que base de datos
    correr, y evita que una cuenta "Administrador" legada quede bloqueada
    de secciones que antes si podia usar.

    Deliberadamente no toca a un usuario que ya pertenece a algun Grupo:
    eso es lo que distingue a un rol intermedio (staff + Grupo acotado) de
    una cuenta legada (staff sin ningun Grupo, que antes de este sistema
    significaba acceso completo). Auto-sanar tambien a un staff con Grupo
    le daria de vuelta el acceso completo y anularia el proposito de
    armarle un rol intermedio.
    """
    if (
        user.is_staff
        and not user.is_superuser
        and not user.groups.exists()
        and not user.has_perms(ADMIN_PERM_CODENAMES)
    ):
        grant_full_admin_permissions(user)
        # `has_perms` ya dejo en cache (en esta misma instancia de request.user)
        # el resultado de antes de otorgar los permisos; sin limpiarlo, el
        # `has_perm` que `require_perms` hace a continuacion, en la misma
        # peticion, seguiria leyendo ese cache viejo y negando el acceso.
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, attr):
                delattr(user, attr)


def staff_required(view_func):
    @never_cache
    @login_required
    @user_passes_test(lambda user: user.is_staff)
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        _self_heal_legacy_admin(request.user)
        return view_func(request, *args, **kwargs)
    return wrapped


def require_perms(*perms):
    """Ademas de ser staff, exige al menos uno de estos permisos.

    Un superusuario siempre pasa (Django resuelve `has_perm` como True
    para superusuarios sin consultar la tabla de permisos). Un staff sin
    ninguno de estos permisos ve un mensaje y vuelve al dashboard: la
    proteccion real esta aqui, en el servidor, no en que el boton se
    muestre o no en la plantilla.
    """
    def decorator(view_func):
        @staff_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not any(request.user.has_perm(perm) for perm in perms):
                messages.error(request, "No tienes permisos para esta accion.")
                return redirect('admin_dashboard')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
