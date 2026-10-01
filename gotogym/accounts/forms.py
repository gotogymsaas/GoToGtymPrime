from django import forms
from orders.colombia_data import DEPARTAMENTOS, municipios_de

from .models import CustomerAddress


class CustomerAddressForm(forms.ModelForm):
    department = forms.ChoiceField(
        label='Departamento',
        choices=[('', 'Selecciona un departamento')] + [(d, d) for d in DEPARTAMENTOS],
    )

    class Meta:
        model = CustomerAddress
        fields = [
            'label', 'full_name', 'phone', 'country', 'department', 'city',
            'postal_code', 'address_line', 'address_complement', 'notes', 'is_default',
        ]

    def clean(self):
        cleaned_data = super().clean()
        departamento = cleaned_data.get('department')
        ciudad = (cleaned_data.get('city') or '').strip()
        if departamento and ciudad and ciudad not in municipios_de(departamento):
            self.add_error('city', 'Selecciona una ciudad valida para el departamento elegido.')
        cleaned_data['city'] = ciudad
        return cleaned_data
