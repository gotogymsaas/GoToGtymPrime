from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0015_factura_alegra'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='coach_can_offer',
            field=models.BooleanField(
                default=False,
                help_text='Quantum Coach puede mencionarlo a cualquier visitante. Úsalo solo para cupones de campaña; '
                          'los de afiliados nunca se ofrecen.',
            ),
        ),
    ]
