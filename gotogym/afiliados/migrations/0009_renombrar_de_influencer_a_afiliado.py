"""Renombra el programa de "influencer" a "afiliado" en modelos, campos y
permisos.

Esta migracion asume que la base ya paso por `afiliados.adaptar_base`, que el
comando `migrate` ejecuta solo antes de empezar: ese paso renombra las tablas
`influencer_*` a `afiliados_*` y reasigna la etiqueta de la app en
`django_migrations` y `django_content_type`. Sin eso, Django vera la app nueva
sin migraciones aplicadas e intentaria crear tablas que ya existen. Aqui se
renombran los modelos (y con ellos sus tablas), las columnas `influencer_id`
y los permisos, conservando a quien los tenia asignados.
"""
from django.conf import settings
from django.db import migrations, models

# modelo viejo -> (modelo nuevo, nombre legible para el permiso)
MODELOS = {
    'influencerprofile': ('perfilafiliado', 'Perfil de afiliado'),
    'influencerprogramsettings': ('configuracionprogramaafiliados', 'Configuracion del programa de afiliados'),
}
ACCIONES = ('add', 'change', 'delete', 'view')


def _mover_permisos(apps, desde_hacia):
    """Renombra el codigo de cada permiso conservando quien lo tiene asignado.

    Si por alguna razon ya existia el permiso con el nombre nuevo, las
    asignaciones (a grupos y a usuarios) pasan a ese y se descarta el viejo.
    """
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('accounts', 'User')
    asignaciones_de_grupo = Group.permissions.through
    asignaciones_de_usuario = User.user_permissions.through

    tipos = list(ContentType.objects.filter(app_label='afiliados').values_list('pk', flat=True))
    for viejo, (nuevo, legible) in desde_hacia.items():
        for accion in ACCIONES:
            codigo_viejo, codigo_nuevo = f'{accion}_{viejo}', f'{accion}_{nuevo}'
            for permiso in Permission.objects.filter(content_type_id__in=tipos, codename=codigo_viejo):
                existente = Permission.objects.filter(
                    content_type_id=permiso.content_type_id, codename=codigo_nuevo,
                ).first()
                if existente is None:
                    permiso.codename = codigo_nuevo
                    permiso.name = f'Can {accion} {legible}'
                    permiso.save(update_fields=['codename', 'name'])
                    continue
                for tabla, campo in ((asignaciones_de_grupo, 'group_id'), (asignaciones_de_usuario, 'user_id')):
                    ya_asignados = set(tabla.objects.filter(permission_id=existente.pk).values_list(campo, flat=True))
                    for fila in tabla.objects.filter(permission_id=permiso.pk):
                        if getattr(fila, campo) in ya_asignados:
                            fila.delete()
                        else:
                            fila.permission_id = existente.pk
                            fila.save(update_fields=['permission'])
                permiso.delete()


def renombrar_permisos(apps, schema_editor):
    _mover_permisos(apps, MODELOS)


def revertir_permisos(apps, schema_editor):
    _mover_permisos(apps, {nuevo: (viejo, viejo) for viejo, (nuevo, _) in MODELOS.items()})


class Migration(migrations.Migration):

    dependencies = [
        ('afiliados', '0008_postulacion_datos_personales_y_redes'),
        # Las migraciones de orders que apuntan al perfil deben correr antes
        # de que el modelo cambie de nombre.
        ('orders', '0008_order_coupon'),
        ('accounts', '0011_user_phone'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RenameModel(old_name='InfluencerProfile', new_name='PerfilAfiliado'),
        migrations.RenameModel(old_name='InfluencerProgramSettings', new_name='ConfiguracionProgramaAfiliados'),
        migrations.RenameField(model_name='commission', old_name='influencer', new_name='afiliado'),
        migrations.RenameField(model_name='withdrawalrequest', old_name='influencer', new_name='afiliado'),
        migrations.RenameField(model_name='referralclick', old_name='influencer', new_name='afiliado'),
        migrations.RenameField(model_name='payoutaccount', old_name='influencer', new_name='afiliado'),
        migrations.RenameField(model_name='socialnetwork', old_name='influencer', new_name='afiliado'),
        migrations.AlterField(
            model_name='perfilafiliado',
            name='user',
            field=models.OneToOneField(
                on_delete=models.deletion.CASCADE, related_name='perfil_afiliado',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name='perfilafiliado',
            options={'verbose_name': 'Perfil de afiliado', 'verbose_name_plural': 'Perfiles de afiliado'},
        ),
        migrations.RunPython(renombrar_permisos, revertir_permisos),
    ]
