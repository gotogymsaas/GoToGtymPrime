from django import forms

from products.models import Brand, Product, ProductCategory


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "brand", "description", "price", "discount", "stock", "featured", "image"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ["name", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name"]
