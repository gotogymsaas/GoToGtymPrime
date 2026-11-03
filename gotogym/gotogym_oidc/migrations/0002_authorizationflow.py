from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('gotogym_oidc', '0001_initial')]
    operations = [migrations.CreateModel(name='AuthorizationFlow', fields=[
        ('digest', models.CharField(max_length=64, primary_key=True, serialize=False)),
        ('expires_at', models.DateTimeField(db_index=True)),
    ])]
