from django.contrib import admin
from .models import FrontendTranslation


@admin.register(FrontendTranslation)
class FrontendTranslationAdmin(admin.ModelAdmin):
    list_display = ("language_code", "namespace", "key", "text")
    list_filter = ("language_code", "namespace")
    search_fields = ("key", "text")
