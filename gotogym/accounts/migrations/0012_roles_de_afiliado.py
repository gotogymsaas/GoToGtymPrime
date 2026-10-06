"""Los campos de usuario del programa de afiliados dejan de llamarse
"influencer"."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_user_phone'),
    ]

    operations = [
        migrations.RenameField(model_name='user', old_name='es_influencer', new_name='es_afiliado'),
        migrations.RenameField(model_name='user', old_name='show_influencer_modal', new_name='show_afiliado_modal'),
        migrations.AlterField(
            model_name='user',
            name='es_afiliado',
            field=models.BooleanField(default=False, verbose_name='Es afiliado'),
        ),
    ]
