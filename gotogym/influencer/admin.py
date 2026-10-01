from django.contrib import admin

from .models import (
    Commission,
    InfluencerProfile,
    InfluencerProgramSettings,
    ReferralClick,
    WithdrawalRequest,
)


@admin.register(InfluencerProfile)
class InfluencerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "referral_code", "status", "is_active", "commission_balance", "created_at")
    list_filter = ("status", "is_active")
    search_fields = ("user__email", "referral_code")


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ("order", "influencer", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("order__order_number", "influencer__user__email")


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("influencer", "amount", "status", "requested_at", "resolved_at")
    list_filter = ("status",)


@admin.register(InfluencerProgramSettings)
class InfluencerProgramSettingsAdmin(admin.ModelAdmin):
    list_display = ("default_commission_rate", "default_customer_discount", "updated_at")


@admin.register(ReferralClick)
class ReferralClickAdmin(admin.ModelAdmin):
    list_display = ("influencer", "created_at")
    list_filter = ("influencer",)
