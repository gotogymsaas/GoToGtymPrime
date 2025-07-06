from django import forms
from .models import Category

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 rounded-xl border border-gray-300 focus:border-[#C5A46B] focus:ring-2 focus:ring-[#C5A46B]/30 bg-white shadow-sm transition placeholder-gray-400 text-gray-800',
                'placeholder': 'Nombre de la categoría',
            }),
        }
