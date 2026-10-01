from django import forms
from orders.colombia_data import DEPARTAMENTOS, municipios_de

from .models import CustomerAddress


class CustomerAddressForm(forms.ModelForm):
    # El catalogo de departamentos/ciudades es solo de Colombia (envios no
    # cubren otros paises todavia), asi que el desplegable de pais tiene una
    # sola opcion real en vez de dejarlo como texto libre.
    country = forms.ChoiceField(label='Pais', choices=[('Colombia', 'Colombia')], initial='Colombia')
    department = forms.ChoiceField(
        label='Departamento',
        choices=[('', 'Selecciona un departamento')] + [(d, d) for d in DEPARTAMENTOS],
    )

    class Meta:
        model = CustomerAddress
        # `label`, `full_name` y `phone` salieron del formulario: duplicaban
        # lo que el usuario ya puso en "Datos personales" (nombre, telefono)
        # y una direccion de entrega es solo el lugar, no un contacto
        # distinto. El formulario completa esos tres a partir del perfil
        # (ver `accounts.views.address_edit`). `is_default` tambien salio:
        # se elige desde la lista de direcciones, no al editar una sola.
        fields = [
            'country', 'department', 'city',
            'postal_code', 'address_line', 'address_complement', 'notes',
        ]
        labels = {
            'country': 'Pais',
            'city': 'Ciudad',
            'postal_code': 'Codigo postal',
            'address_line': 'Direccion',
            'address_complement': 'Complemento (apto, torre, etc.)',
            'notes': 'Notas de entrega',
        }

    def clean(self):
        cleaned_data = super().clean()
        departamento = cleaned_data.get('department')
        ciudad = (cleaned_data.get('city') or '').strip()
        if departamento and ciudad and ciudad not in municipios_de(departamento):
            self.add_error('city', 'Selecciona una ciudad valida para el departamento elegido.')
        cleaned_data['city'] = ciudad
        return cleaned_data
