import os

from django.contrib.auth.hashers import make_password
from django.db import migrations


def bootstrap_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    if User.objects.filter(is_staff=True).exists():
        return

    email = os.environ.get("GOTOGYM_ADMIN_EMAIL", "admin@gotogym.com").strip().lower()
    username = os.environ.get("GOTOGYM_ADMIN_USERNAME", "ericviana").strip()
    password = os.environ.get("GOTOGYM_ADMIN_PASSWORD", "EricViana@2026")

    user, _ = User.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "first_name": "Eric",
            "last_name": "Viana",
        },
    )
    user.username = user.username or username
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.password = make_password(password)
    user.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_es_influencer"),
    ]

    operations = [
        migrations.RunPython(bootstrap_admin, noop),
    ]
