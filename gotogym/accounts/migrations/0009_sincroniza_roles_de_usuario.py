from django.db import migrations

# Copia deliberada de administracion.permissions.ADMIN_PERM_SPECS: una
# migracion de datos no debe importar codigo de la app (puede cambiar de
# forma incompatible con lo que esta migracion espera), solo modelos
# historicos via `apps.get_model`. Si ADMIN_PERM_SPECS cambia mas adelante,
# esta copia queda congelada en el tiempo, que es lo correcto para una
# migracion ya aplicada.
PERM_SPECS = [
    ("products", "add_product"),
    ("products", "change_product"),
    ("products", "delete_product"),
    ("products", "add_producttag"),
    ("products", "change_producttag"),
    ("products", "delete_producttag"),
    ("products", "add_productcategory"),
    ("products", "delete_productcategory"),
    ("products", "add_brand"),
    ("products", "delete_brand"),
    ("inventory", "change_inventory"),
    ("orders", "add_coupon"),
    ("orders", "change_coupon"),
    ("orders", "delete_coupon"),
    ("accounts", "change_user"),
    ("accounts", "delete_user"),
    ("auth", "add_group"),
    ("auth", "change_group"),
    ("auth", "delete_group"),
    ("administracion", "change_panelsettings"),
]

# Cuentas a promover al rol de mayor jerarquia. Solo promueve cuentas que
# ya existan (creadas por signup normal): no inventa contrasena ni datos
# de perfil, a diferencia de `0006_ensure_admin_user`, que si crea la
# cuenta si falta porque esa es una cuenta de servicio, no la de una
# persona real.
CUENTAS_A_PROMOVER = [
    "andresmarinc@gmail.com",
]


def sincronizar_roles(apps, schema_editor):
    from django.db.models import Q

    User = apps.get_model("accounts", "User")
    Permission = apps.get_model("auth", "Permission")

    query = Q()
    for app_label, codename in PERM_SPECS:
        query |= Q(content_type__app_label=app_label, codename=codename)
    permisos = list(Permission.objects.filter(query))

    for email in CUENTAS_A_PROMOVER:
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            continue

        user.is_staff = True
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])
        user.user_permissions.add(*permisos)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_alter_user_first_name_alter_user_last_name"),
        ("administracion", "0001_initial"),
        ("products", "0013_backfill_media_from_legacy_image"),
        ("inventory", "0002_seed_inventory_from_product_stock"),
        ("orders", "0005_alter_order_order_status"),
    ]

    operations = [
        migrations.RunPython(sincronizar_roles, noop),
    ]
