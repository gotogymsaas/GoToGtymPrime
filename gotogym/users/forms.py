from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group
from .models import UserProfile

class CustomUserCreationForm(UserCreationForm):
    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Grupo",
        help_text="Selecciona el grupo al que pertenece este usuario."
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'group']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['nit', 'phone', 'logo', 'contact_name', 'position', 'empresa']
