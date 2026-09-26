from django.db import migrations

LEGACY_CODE = "CUPON"


def seed_coupon(apps, schema_editor):
    Coupon = apps.get_model("orders", "Coupon")
    Coupon.objects.get_or_create(
        code=LEGACY_CODE,
        defaults={
            "discount_type": "percentage",
            "value": 10,
            "is_active": True,
        },
    )


def remove_coupon(apps, schema_editor):
    Coupon = apps.get_model("orders", "Coupon")
    Coupon.objects.filter(code=LEGACY_CODE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_coupon"),
    ]

    operations = [
        migrations.RunPython(seed_coupon, remove_coupon),
    ]
