from django.contrib import admin

from .models import Product, ProductCategory, ProductFavorite, ProductReview


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["name", "description"]

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ["name", "description"]
    list_display = ["name", "category", "line", "base_price", "stock"]
    list_filter = ["category", "line"]
    autocomplete_fields = ["category"]


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'rating', 'user', 'order_item', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['product__name', 'user__email', 'comment']
    readonly_fields = ['product', 'order_item', 'user']


@admin.register(ProductFavorite)
class ProductFavoriteAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['product__name', 'user__email']
    readonly_fields = ['product', 'user', 'created_at']
