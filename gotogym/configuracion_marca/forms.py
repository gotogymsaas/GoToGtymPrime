from django import forms
from .models import ColorMarca

class ColorMarcaForm(forms.ModelForm):
    class Meta:
        model = ColorMarca
        fields = ['nombre', 'codigo_hex', 'descripcion']
        widgets = {
            'codigo_hex': forms.TextInput(attrs={'type': 'color', 'class': 'w-16 h-10 p-0 border-0 bg-transparent'}),
        }
