from django import forms

from .models import SolicitudAtencion
from .services import MAX_MENSAJE


class SolicitudForm(forms.Form):
    nombre = forms.CharField(max_length=120)
    email = forms.EmailField(max_length=254)
    motivo = forms.ChoiceField(choices=SolicitudAtencion.Motivo.choices)
    mensaje = forms.CharField(max_length=MAX_MENSAJE, min_length=5)
    acepta_contacto = forms.BooleanField(required=True)
