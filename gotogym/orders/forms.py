"""Formulario de checkout: datos de contacto y de entrega.

La validacion vive aqui, no en los atributos HTML: el navegador puede
saltarselos y la peticion puede llegar sin pasar por el formulario.
"""
import re

from django import forms
from django.utils.translation import gettext_lazy as _

from .colombia_data import DEPARTAMENTOS, municipios_de

TELEFONO_VALIDO = re.compile(r'^[0-9+()\s-]{7,20}$')


class CheckoutForm(forms.Form):
    first_name = forms.CharField(label=_('Nombre'), max_length=100)
    last_name = forms.CharField(label=_('Apellido'), max_length=100)
    email = forms.EmailField(label=_('Correo electrónico'))
    phone = forms.CharField(label=_('Teléfono'), max_length=40)

    country = forms.CharField(label=_('País'), max_length=80, initial='Colombia')
    department = forms.ChoiceField(
        label=_('Departamento'),
        # La opcion en blanco fuerza una eleccion explicita: sin ella, el
        # navegador preselecciona visualmente la primera opcion de la lista
        # (Amazonas) y un usuario que no toque el campo terminaria enviando
        # ese valor sin haberlo elegido.
        choices=[('', _('Selecciona un departamento'))] + [(d, d) for d in DEPARTAMENTOS],
    )
    # No es un ChoiceField: las opciones dependen del departamento elegido
    # (se llenan en el navegador con JS). La integridad real se valida en
    # clean(), cruzando city contra el departamento ya validado.
    city = forms.CharField(label=_('Ciudad'), max_length=80)
    postal_code = forms.CharField(label=_('Código postal'), max_length=20, required=False)
    address_line = forms.CharField(label=_('Dirección'), max_length=255)
    address_complement = forms.CharField(
        label=_('Complemento (apartamento, torre, referencia)'), max_length=255, required=False,
    )
    notes = forms.CharField(
        label=_('Información adicional para la entrega'), required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not TELEFONO_VALIDO.match(phone):
            raise forms.ValidationError(
                'Escribe un telefono valido: entre 7 y 20 caracteres, solo numeros y + ( ) - espacios.'
            )
        return phone

    def clean_first_name(self):
        return self._texto_no_vacio('first_name', 'Escribe tu nombre.')

    def clean_last_name(self):
        return self._texto_no_vacio('last_name', 'Escribe tu apellido.')

    def clean_address_line(self):
        direccion = self.cleaned_data['address_line'].strip()
        if len(direccion) < 5:
            raise forms.ValidationError('La direccion es demasiado corta.')
        return direccion

    def clean(self):
        cleaned_data = super().clean()
        departamento = cleaned_data.get('department')
        ciudad = cleaned_data.get('city', '').strip()
        if departamento and ciudad and ciudad not in municipios_de(departamento):
            self.add_error(
                'city',
                'Selecciona una ciudad valida para el departamento elegido.',
            )
        cleaned_data['city'] = ciudad
        return cleaned_data

    def _texto_no_vacio(self, campo, mensaje):
        valor = self.cleaned_data[campo].strip()
        if not valor:
            raise forms.ValidationError(mensaje)
        return valor
