"""Otorga los permisos nuevos de pedidos y usuarios a quienes ya tenian el
paquete completo del panel, para que nadie pierda acceso cuando las vistas
empiecen a exigirlos.

Solo cubre a quien tiene el paquete anterior asignado directamente. Los roles
intermedios (grupos) no reciben nada: fueron armados para tareas concretas y
quien los administra decide si deben ver pedidos o usuarios."""
from django.conf import settings
from django.db import migrations

PAQUETE_ANTERIOR = [
    ('products', 'add_product'), ('products', 'change_product'), ('products', 'delete_product'),
    ('products', 'add_producttag'), ('products', 'change_producttag'), ('products', 'delete_producttag'),
    ('products', 'add_productcategory'), ('products', 'delete_productcategory'),
    ('products', 'add_brand'), ('products', 'delete_brand'),
    ('inventory', 'change_inventory'),
    ('orders', 'add_coupon'), ('orders', 'change_coupon'), ('orders', 'delete_coupon'),
    ('accounts', 'change_user'), ('accounts', 'delete_user'),
    ('auth', 'add_group'), ('auth', 'change_group'), ('auth', 'delete_group'),
    ('administracion', 'change_panelsettings'),
    ('afiliados', 'change_perfilafiliado'), ('afiliados', 'delete_perfilafiliado'),
    ('afiliados', 'change_withdrawalrequest'), ('afiliados', 'change_configuracionprogramaafiliados'),
    ('afiliados', 'change_commission'),
    ('afiliados', 'add_recursomarca'), ('afiliados', 'change_recursomarca'), ('afiliados', 'delete_recursomarca'),
    ('payments', 'add_refund'),
]
PERMISOS_NUEVOS = [('orders', 'view_order'), ('orders', 'change_order'), ('accounts', 'view_user')]


def otorgar(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    User = apps.get_model(settings.AUTH_USER_MODEL)

    def permisos(pares):
        buscados = set(pares)
        return {
            (p.content_type.app_label, p.codename): p
            for p in Permission.objects.select_related('content_type')
            if (p.content_type.app_label, p.codename) in buscados
        }

    anteriores = permisos(PAQUETE_ANTERIOR)
    nuevos = list(permisos(PERMISOS_NUEVOS).values())
    if not nuevos or len(anteriores) < len(PAQUETE_ANTERIOR):
        # Base sin los permisos creados todavia (por ejemplo una base nueva):
        # no hay cuentas que proteger.
        return
    ids_anteriores = {p.pk for p in anteriores.values()}
    for usuario in User.objects.filter(is_staff=True, is_superuser=False):
        asignados = set(usuario.user_permissions.values_list('pk', flat=True))
        if ids_anteriores <= asignados:
            usuario.user_permissions.add(*nuevos)


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0008_accion_de_panel'),
        ('auth', '0012_alter_user_first_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(otorgar, migrations.RunPython.noop)]
