from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'brand', 'description', 'price', 'discount', 'stock', 'featured', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
