from django.contrib import admin

from products.models import Product, Category

class ProductAdmin(admin.ModelAdmin):
    model = Product
    list_display=['name',
    'description',
    'price',
    'stock',
    'category',
    'is_active',
    'created_at',
    'updated_at',
    ]
    search_fields=['name'
    ]

admin.site.register(Product, ProductAdmin)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)
