from django.contrib import admin
from .models import Category, Post

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]
    list_display = ["name", "slug"]

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ["title", "excerpt", "content"]
    list_display = ["title", "author", "category", "published", "is_published"]
    list_filter = ["category", "author", "is_published"]
    autocomplete_fields = ["author", "category"]
    date_hierarchy = "published"
