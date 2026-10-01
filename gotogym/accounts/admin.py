from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomerAddress, CustomerSegment, User


@admin.register(CustomerSegment)
class CustomerSegmentAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "is_default", "created_at")
    list_filter = ("is_default",)
    search_fields = ("user__email", "full_name", "city")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "age", "accepted_terms", "terms_accepted_at", "terms_hash", "show_influencer_modal", "es_influencer", "customer_segments")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "first_name", "last_name", "age", "password1", "password2", "accepted_terms", "show_influencer_modal", "es_influencer"),
        }),
    )
    list_display = ("email", "first_name", "last_name", "age", "is_staff", "accepted_terms", "show_influencer_modal", "es_influencer")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions", "customer_segments")
