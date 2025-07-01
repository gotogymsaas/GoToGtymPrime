from django.db import models
from django.conf import settings
import uuid

def generate_referral_code():
    return str(uuid.uuid4())

class InfluencerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='influencer_profile')
    referral_code = models.CharField(max_length=36, unique=True, default=generate_referral_code)
    commission_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_referred = models.PositiveIntegerField(default=0)
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Influencer: {self.user.email} ({self.referral_code})"
