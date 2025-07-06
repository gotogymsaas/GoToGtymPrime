from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'author', 'category', 'excerpt', 'content', 'featured']  # Eliminar 'slug' del formulario
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input w-full'}),
            'author': forms.Select(attrs={'class': 'form-select w-full'}),
            'category': forms.Select(attrs={'class': 'form-select w-full'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-textarea w-full', 'rows': 2}),
            'content': forms.Textarea(attrs={'class': 'form-textarea w-full', 'rows': 6}),
        }
