from django import forms
from blog.models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title','slug', 'author', 'category', 'excerpt',  'body', 'featured',  ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-lg border border-gray-300'}),
            'slug': forms.TextInput(attrs={'class': 'w-full px-4 py-2 rounded-lg border border-gray-300'}),
            'author': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-lg border border-gray-300'}),
            'category': forms.Select(attrs={'class': 'w-full px-4 py-2 rounded-lg border border-gray-300'}),
            'excerpt': forms.Textarea(attrs={'class': 'w-full px-4 py-2 rounded-lg border border-gray-300', 'rows': 2}),
            'body': forms.Textarea(attrs={'class': 'w-full px-4 py-2 rounded-lg border border-gray-300', 'rows': 6}),
            "featured": forms.ClearableFileInput(attrs={"class": "hidden","accept": "image/*",}),
        }