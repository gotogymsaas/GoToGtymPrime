from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "age", "accepted_terms", "terms_accepted_at", "terms_hash", "show_influencer_modal")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "first_name", "last_name", "age", "password1", "password2", "accepted_terms", "show_influencer_modal"),
        }),
    )
    list_display = ("email", "first_name", "last_name", "age", "is_staff", "accepted_terms", "show_influencer_modal")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
