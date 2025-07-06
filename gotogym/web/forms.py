from django import forms
from .models import TemplateConfig

class TemplateConfigForm(forms.ModelForm):
    class Meta:
        model = TemplateConfig
        fields = ['template_name', 'color', 'image', 'font']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}),
        }
