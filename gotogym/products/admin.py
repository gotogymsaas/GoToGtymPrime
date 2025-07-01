from django.contrib import admin
from .models import ProductCategory, Product

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["name", "description"]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ["name", "description"]
    list_display = ["name", "category", "price", "stock"]
    list_filter = ["category"]
    autocomplete_fields = ["category"]
