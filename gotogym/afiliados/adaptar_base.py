"""Paso previo a `migrate` cuando la base viene de cuando el programa se
llamaba "influencer".

La app cambio de etiqueta (`influencer` -> `afiliados`). Django guarda esa
etiqueta en `django_migrations` (que migraciones se aplicaron) y en
`django_content_type` (de ahi cuelgan los permisos), y las tablas se llaman
`<etiqueta>_<modelo>`. Sin este paso, `migrate` veria la app `afiliados` sin
nada aplicado, daria `InconsistentMigrationHistory` en las migraciones de
`orders` que dependen de ella, y de todos modos intentaria crear tablas que ya
existen.

Es idempotente: si ya se hizo (o la base es nueva) no cambia nada. Todo ocurre
en una sola transaccion donde el motor lo permite (PostgreSQL y SQLite).
"""
from django.core.management.base import CommandError
from django.db import transaction

ETIQUETA_ANTIGUA = 'influencer'
ETIQUETA_NUEVA = 'afiliados'


def adaptar_base(connection, escribir=None):
    """Renombra tablas y registros de la app antigua. Devuelve True si hizo algo."""
    escribir = escribir or (lambda texto: None)
    with connection.cursor() as cursor:
        tablas = set(connection.introspection.table_names(cursor))
        if 'django_migrations' not in tablas:
            return False
        cursor.execute('SELECT COUNT(*) FROM django_migrations WHERE app = %s', [ETIQUETA_ANTIGUA])
        con_etiqueta_antigua = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM django_migrations WHERE app = %s', [ETIQUETA_NUEVA])
        con_etiqueta_nueva = cursor.fetchone()[0]
    if not con_etiqueta_antigua:
        return False
    if con_etiqueta_nueva:
        raise CommandError(
            f'django_migrations tiene registros de "{ETIQUETA_ANTIGUA}" y de "{ETIQUETA_NUEVA}" a la vez: '
            'la base esta a medio renombrar y hay que revisarla a mano antes de seguir.'
        )

    prefijo = f'{ETIQUETA_ANTIGUA}_'
    por_renombrar = sorted(t for t in tablas if t.startswith(prefijo))
    choques = [t for t in por_renombrar if f'{ETIQUETA_NUEVA}_{t[len(prefijo):]}' in tablas]
    if choques:
        raise CommandError(f'Ya existen las tablas destino de: {", ".join(choques)}.')

    quote = connection.ops.quote_name
    with transaction.atomic(using=connection.alias), connection.cursor() as cursor:
        for tabla in por_renombrar:
            nueva = f'{ETIQUETA_NUEVA}_{tabla[len(prefijo):]}'
            cursor.execute(f'ALTER TABLE {quote(tabla)} RENAME TO {quote(nueva)}')
            escribir(f'  tabla {tabla} -> {nueva}')
        cursor.execute(
            'UPDATE django_migrations SET app = %s WHERE app = %s', [ETIQUETA_NUEVA, ETIQUETA_ANTIGUA],
        )
        if 'django_content_type' in tablas:
            cursor.execute(
                'UPDATE django_content_type SET app_label = %s WHERE app_label = %s',
                [ETIQUETA_NUEVA, ETIQUETA_ANTIGUA],
            )
    escribir(f'  {len(por_renombrar)} tablas, migraciones y tipos de contenido pasan de "{ETIQUETA_ANTIGUA}" a "{ETIQUETA_NUEVA}".')
    return True
