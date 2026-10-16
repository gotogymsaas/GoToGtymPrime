from django import forms
from django.utils.translation import gettext_lazy

from .models import ProductReview


class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.RadioSelect(choices=[(value, f'{value} estrellas') for value in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': gettext_lazy('Cuéntanos tu experiencia (opcional).')}),
        }

    def clean_rating(self):
        rating = self.cleaned_data['rating']
        return int(rating)