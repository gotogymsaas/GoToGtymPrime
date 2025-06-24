<<<<<<< HEAD
from django.contrib import admin

from products.models import Product

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
=======
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
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
