from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='show_influencer_modal',
            field=models.BooleanField(default=True),
        ),
    ]
