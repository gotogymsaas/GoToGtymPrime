"""Serializers for influencer API."""
from rest_framework import serializers

from .models import InfluencerProfile


class InfluencerStatsSerializer(serializers.ModelSerializer):
    """Serializer used by the optional stats API."""

    class Meta:
        model = InfluencerProfile
        fields = [
            "referral_code",
            "total_referred_users",
            "total_sales_value",
            "commission_earned",
            "wallet_balance",
        ]
