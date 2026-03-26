from django.db import migrations, models, connection


def add_column_if_not_exists(apps, schema_editor):
    db_vendor = connection.vendor  # 'sqlite', 'postgresql', 'mysql'
    with connection.cursor() as cursor:
        if db_vendor == 'sqlite':
            cursor.execute("PRAGMA table_info(accounts_user)")
            cols = [row[1] for row in cursor.fetchall()]
            if 'show_influencer_modal' not in cols:
                cursor.execute(
                    "ALTER TABLE accounts_user ADD COLUMN show_influencer_modal boolean NOT NULL DEFAULT 1"
                )
        else:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='accounts_user' AND column_name='show_influencer_modal'"
            )
            if not cursor.fetchone():
                cursor.execute(
                    "ALTER TABLE accounts_user ADD COLUMN show_influencer_modal boolean NOT NULL DEFAULT true"
                )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_column_if_not_exists, noop),
    ]

