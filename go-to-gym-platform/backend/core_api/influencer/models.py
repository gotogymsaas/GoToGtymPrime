"""Influencer app models for referral tracking."""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class InfluencerProfile(models.Model):
    """Stores influencer metrics and wallet info for a user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="influencer_profile")
    referral_code = models.CharField(max_length=50, unique=True)
    total_referred_users = models.PositiveIntegerField(default=0)
    total_sales_value = models.FloatField(default=0.0)
    commission_earned = models.FloatField(default=0.0)
    wallet_balance = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user} - {self.referral_code}"


class ReferralTransaction(models.Model):
    """Represents a single referred sale processed through the platform."""

    influencer = models.ForeignKey(InfluencerProfile, on_delete=models.CASCADE, related_name="transactions")
    referred_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    sale_amount = models.FloatField()
    commission_amount = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.influencer.referral_code}: {self.sale_amount}"
