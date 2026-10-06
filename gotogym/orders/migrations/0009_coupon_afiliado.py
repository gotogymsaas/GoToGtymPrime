"""El cupon de un afiliado apunta a `afiliado` (antes `influencer`)."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_order_coupon'),
        ('afiliados', '0009_renombrar_de_influencer_a_afiliado'),
    ]

    operations = [
        migrations.RenameField(model_name='coupon', old_name='influencer', new_name='afiliado'),
    ]
