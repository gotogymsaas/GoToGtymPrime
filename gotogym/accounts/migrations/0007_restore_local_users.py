"""Restauraba en cada base nueva a ocho personas reales (correo, nombre, edad,
fechas de acceso y el hash de su contrasena) con datos escritos en el codigo.

Datos personales no pertenecen a una migracion: quedaban en el repositorio y en
todo entorno nuevo, incluidas las bases de pruebas. Se retiraron; la migracion
se conserva porque ya esta registrada como aplicada en las bases existentes,
y para ellas no cambia nada (una migracion aplicada no vuelve a ejecutarse).
"""
from django.db import migrations
from django.utils.dateparse import parse_datetime

USERS: list[dict] = []


def unique_username(User, username, email):
    candidate = username or email
    if not User.objects.filter(username=candidate).exclude(email=email).exists():
        return candidate

    base = email.split("@", 1)[0]
    candidate = base
    counter = 2
    while User.objects.filter(username=candidate).exclude(email=email).exists():
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


def restore_users(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for item in USERS:
        user, _ = User.objects.get_or_create(email=item["email"])
        user.username = unique_username(User, item["username"], item["email"])
        user.first_name = item["first_name"]
        user.last_name = item["last_name"]
        user.age = item["age"]
        user.password = item["password"]
        user.is_active = item["is_active"]
        user.is_staff = item["is_staff"]
        user.is_superuser = item["is_superuser"]
        user.accepted_terms = item["accepted_terms"]
        user.terms_accepted_at = parse_datetime(item["terms_accepted_at"]) if item["terms_accepted_at"] else None
        user.terms_hash = item["terms_hash"]
        user.show_influencer_modal = item["show_influencer_modal"]
        user.es_influencer = item["es_influencer"]
        user.date_joined = parse_datetime(item["date_joined"])
        user.last_login = parse_datetime(item["last_login"]) if item["last_login"] else None
        user.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_ensure_admin_user"),
    ]

    operations = [
        migrations.RunPython(restore_users, noop),
    ]
