<<<<<<< HEAD
from django.contrib import admin
from .models import Company, Brand


class BrandInlineAdmin(admin.TabularInline):
    model = Brand
    extra = 0
    verbose_name = "Marca"
    verbose_name_plural = "Marcas"


class CompanyAdmin(admin.ModelAdmin):
    model = Company
    list_display = [ "name", "identifier", "get_administrators", "created_at", "updated_at", ]
    search_fields = ["name", "identifier"]
    inlines = [BrandInlineAdmin]

    def get_administrators(self, obj):
        """Mostrar los administradores asociados."""
        return ", ".join([admin.username for admin in obj.administrators.all()])

    get_administrators.short_description = "Administradores"


admin.site.register(Company, CompanyAdmin)
=======
from django.contrib import admin
from .models import Company, Brand


class BrandInlineAdmin(admin.TabularInline):
    model = Brand
    extra = 0
    verbose_name = "Marca"
    verbose_name_plural = "Marcas"


class CompanyAdmin(admin.ModelAdmin):
    model = Company
    list_display = [ "name", "identifier", "get_administrators", "created_at", "updated_at", ]
    search_fields = ["name", "identifier"]
    inlines = [BrandInlineAdmin]

    def get_administrators(self, obj):
        """Mostrar los administradores asociados."""
        return ", ".join([admin.username for admin in obj.administrators.all()])

    get_administrators.short_description = "Administradores"


admin.site.register(Company, CompanyAdmin)
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
