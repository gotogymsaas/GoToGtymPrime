"""Encender el modo "Confirmar sin pagar (equipo)" pasa a exigir su propio
permiso (`toggle_test_mode`) en vez de `change_panelsettings`. Para que nadie
pierda el acceso que ya tenia, se otorga a los grupos y a las cuentas que hoy
tienen `change_panelsettings`.

Tambien fecha el modo si ya estaba encendido: sin fecha se consideraria
vencido, y con la ultima modificacion de la configuracion como punto de partida
vence 24 horas despues de ese momento, no mas tarde."""
from django.conf import settings
from django.db import migrations


def otorgar(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model(settings.AUTH_USER_MODEL)
    PanelSettings = apps.get_model('administracion', 'PanelSettings')

    # Los permisos se crean despues de migrar (senal post_migrate): en una base
    # nueva o recien actualizada todavia no existen, asi que se crean aqui. El
    # post_migrate posterior los encuentra y no los duplica.
    tipo, _ = ContentType.objects.get_or_create(app_label='administracion', model='panelsettings')
    nuevo, _ = Permission.objects.get_or_create(
        content_type=tipo, codename='toggle_test_mode',
        defaults={'name': 'Puede encender el modo "Confirmar sin pagar (equipo)"'},
    )
    actual = Permission.objects.filter(content_type=tipo, codename='change_panelsettings').first()
    if actual is not None:
        for grupo in Group.objects.filter(permissions=actual):
            grupo.permissions.add(nuevo)
        for usuario in User.objects.filter(user_permissions=actual):
            usuario.user_permissions.add(nuevo)

    for fila in PanelSettings.objects.filter(
        staff_checkout_without_payment=True, staff_checkout_without_payment_since__isnull=True,
    ):
        PanelSettings.objects.filter(pk=fila.pk).update(staff_checkout_without_payment_since=fila.updated_at)


class Migration(migrations.Migration):

    dependencies = [
        ('administracion', '0012_modo_de_pruebas_vigencia_y_permiso'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(otorgar, migrations.RunPython.noop)]
