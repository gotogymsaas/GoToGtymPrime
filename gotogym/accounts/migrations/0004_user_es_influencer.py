from django.db import migrations, models


def sync_existing_influencers(apps, schema_editor):
    table_names = schema_editor.connection.introspection.table_names()
    if "influencer_influencerprofile" not in table_names:
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM influencer_influencerprofile")
        user_ids = [row[0] for row in cursor.fetchall()]

    if user_ids:
        User = apps.get_model("accounts", "User")
        User.objects.filter(id__in=user_ids).update(es_influencer=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_first_name_alter_user_last_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="es_influencer",
            field=models.BooleanField(default=False, verbose_name="Es influencer"),
        ),
        migrations.RunPython(sync_existing_influencers, noop),
    ]
