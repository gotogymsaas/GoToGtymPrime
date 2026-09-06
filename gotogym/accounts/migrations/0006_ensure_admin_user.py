import os

from django.contrib.auth.hashers import make_password
from django.db import migrations


def ensure_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
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
    user.first_name = user.first_name or "Eric"
    user.last_name = user.last_name or "Viana"
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.password = make_password(password)
    user.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_bootstrap_admin_user"),
    ]

    operations = [
        migrations.RunPython(ensure_admin, noop),
    ]
