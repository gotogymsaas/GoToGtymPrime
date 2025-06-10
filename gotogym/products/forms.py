
from django import forms
from .models import Product, Category


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [  "name", "description", "price", "stock", "category", "image", "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe el producto"}),
            "price": forms.NumberInput(attrs={"step": "0.01", "placeholder": "Precio del producto"}),
            "stock": forms.NumberInput(attrs={"placeholder": "Cantidad en inventario"}),
            "is_active": forms.CheckboxInput(),
            "image": forms.ClearableFileInput(attrs={"class": "hidden","accept": "image/*",}),
        }

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is None or price <= 0:
            raise forms.ValidationError("El precio debe ser mayor a 0.")
        return price


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Nombre de la categoría"}),
            "description": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Descripción opcional"}
            ),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if not name.isalpha():
            raise forms.ValidationError(
                "El nombre de la categoría debe contener solo letras."
            )
        return name
