from django.contrib import admin

from .models import (
    Commission,
    ConfiguracionProgramaAfiliados,
    PerfilAfiliado,
    ReferralClick,
    WithdrawalRequest,
)


@admin.register(PerfilAfiliado)
class PerfilAfiliadoAdmin(admin.ModelAdmin):
    list_display = ("user", "referral_code", "status", "is_active", "commission_balance", "created_at")
    list_filter = ("status", "is_active")
    search_fields = ("user__email", "referral_code")


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ("order", "afiliado", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("order__order_number", "afiliado__user__email")


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("afiliado", "amount", "status", "requested_at", "resolved_at")
    list_filter = ("status",)


@admin.register(ConfiguracionProgramaAfiliados)
class ConfiguracionProgramaAfiliadosAdmin(admin.ModelAdmin):
    list_display = ("default_commission_rate", "default_customer_discount", "updated_at")


@admin.register(ReferralClick)
class ReferralClickAdmin(admin.ModelAdmin):
    list_display = ("afiliado", "created_at")
    list_filter = ("afiliado",)
