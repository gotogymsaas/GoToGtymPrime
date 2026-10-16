import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext, gettext_lazy

from .models import DocumentType, PayoutAccount, PerfilAfiliado, SocialPlatform

TELEFONO_VALIDO = re.compile(r'^[0-9+()\s-]{7,20}$')
DOCUMENTO_VALIDO = re.compile(r'^[A-Za-z0-9]{5,20}$')
LLAVE_ALFANUMERICA = re.compile(r'^@[A-Za-z0-9]{4,20}$')
CELULAR_CON_PREFIJO = re.compile(r'^57(3\d{9})$')
CODIGO_REFERIDO_REGEX = re.compile(r'^[A-Z0-9]{4,20}$')
USUARIO_DE_RED = re.compile(r'^[\w.\-]{2,60}$')
MAX_REDES = 15
MAX_SEGUIDORES = 2_000_000_000

CAMPOS_PERSONALES = ('first_name', 'last_name', 'phone', 'address', 'document_type', 'document_number')
ETIQUETAS_PERSONALES = {
    'first_name': gettext_lazy('Nombre'),
    'last_name': gettext_lazy('Apellido'),
    'phone': gettext_lazy('Telefono'),
    'address': gettext_lazy('Direccion'),
    'document_number': gettext_lazy('Numero de documento'),
}


def normalizar_llave(llave):
    """Devuelve la llave en su forma canonica o lanza ValidationError.

    El afiliado no dice de que tipo es: se reconoce por su forma. Un correo
    lleva "@" en medio; un codigo alfanumerico de Bre-B empieza por "@"; lo
    demas es un numero (documento o celular) o un codigo sin arroba. La forma
    canonica evita que "300 123 4567", "+57 3001234567" y "3001234567" cuenten
    como tres llaves distintas al pagar."""
    llave = llave.strip()
    if '@' in llave[1:]:
        validate_email(llave)
        return llave.lower()
    if llave.startswith('@'):
        if not LLAVE_ALFANUMERICA.fullmatch(llave):
            raise ValidationError(gettext('Una llave que empieza por @ lleva despues de 4 a 20 letras o numeros, sin espacios.'))
        return llave
    # Los separadores (espacios, puntos, guiones, parentesis) solo se
    # perdonan en un numero; en un codigo con letras un espacio es un error.
    es_numero = re.fullmatch(r'[0-9+()\s.-]+', llave)
    sin_separadores = re.sub(r'[\s()+.-]', '', llave) if es_numero else llave
    celular = CELULAR_CON_PREFIJO.fullmatch(sin_separadores)
    if celular:
        return celular.group(1)
    if not DOCUMENTO_VALIDO.fullmatch(sin_separadores):
        raise ValidationError(
            gettext('Escribe tu llave tal como la creaste en tu banco: documento, celular, correo o codigo con @.')
        )
    return sin_separadores


def codigo_referido_disponible(codigo, excluir_profile_pk=None):
    """El codigo elegido por el afiliado tambien se vuelve `Coupon.code` al
    aprobarse (ver `afiliados.services._ensure_personal_coupon`), asi que
    debe ser unico contra ambas tablas antes de aceptarlo."""
    from orders.models import Coupon

    perfiles = PerfilAfiliado.objects.filter(referral_code=codigo)
    if excluir_profile_pk:
        perfiles = perfiles.exclude(pk=excluir_profile_pk)
    if perfiles.exists():
        return False
    return not Coupon.objects.filter(code=codigo).exists()


class DatosPersonalesForm(forms.ModelForm):
    """Identidad de la persona (nombre, contacto y documento). La comparten la
    postulacion y la cuenta de pago para pedir y validar lo mismo igual."""

    document_type = forms.ChoiceField(
        label=gettext_lazy('Tipo de documento'),
        choices=[('', 'Selecciona un tipo')] + list(DocumentType.choices),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # En el perfil estos campos son `blank=True` solo para tolerar a los
        # afiliados anteriores a que se pidieran; en el formulario siempre
        # son obligatorios.
        for nombre in CAMPOS_PERSONALES:
            self.fields[nombre].required = True

    def clean_phone(self):
        telefono = self.cleaned_data['phone'].strip()
        if not TELEFONO_VALIDO.match(telefono):
            raise ValidationError(
                gettext('Escribe un telefono valido: entre 7 y 20 caracteres, solo numeros y + ( ) - espacios.')
            )
        return telefono

    def clean_document_number(self):
        numero = re.sub(r'[\s.\-]', '', self.cleaned_data['document_number'])
        if not DOCUMENTO_VALIDO.fullmatch(numero):
            raise ValidationError(gettext('Escribe el documento de 5 a 20 letras o numeros, sin puntos ni espacios.'))
        return numero.upper()


class PayoutAccountForm(DatosPersonalesForm):
    accept_terms = forms.BooleanField(
        required=True,
        error_messages={'required': gettext_lazy('Debes aceptar los terminos para inscribir tu cuenta.')},
    )
    accept_data = forms.BooleanField(
        required=True,
        error_messages={'required': gettext_lazy('Debes autorizar el tratamiento de tus datos para inscribir tu cuenta.')},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Quien ya acepto los terminos y la autorizacion de datos al inscribir
        # su cuenta no tiene que repetirlo cada vez que la actualiza.
        cuenta = self.instance
        self.ya_acepto = bool(cuenta.pk and cuenta.terms_accepted_at and cuenta.data_consent_at)
        if self.ya_acepto:
            self.fields['accept_terms'].required = False
            self.fields['accept_data'].required = False

    class Meta:
        model = PayoutAccount
        fields = [*CAMPOS_PERSONALES, 'breb_key']
        labels = {**ETIQUETAS_PERSONALES, 'breb_key': 'Llave Bre-B'}

    def clean_breb_key(self):
        return normalizar_llave(self.cleaned_data['breb_key'])


class PostulacionForm(DatosPersonalesForm):
    """Postulacion al programa: datos personales, codigo de afiliado y
    aceptacion de los terminos. Las redes sociales van en `RedSocialFormSet`."""

    referral_code = forms.CharField(
        label=gettext_lazy('Tu codigo de afiliado'), max_length=20,
        error_messages={'required': gettext_lazy('Elige un codigo para tu marca.')},
    )
    accept_terms = forms.BooleanField(
        required=True,
        error_messages={'required': gettext_lazy('Debes aceptar los terminos del programa para continuar.')},
    )

    class Meta:
        model = PerfilAfiliado
        fields = [*CAMPOS_PERSONALES, 'referral_code']
        labels = ETIQUETAS_PERSONALES

    def clean_referral_code(self):
        codigo = self.cleaned_data['referral_code'].strip().upper()
        if not CODIGO_REFERIDO_REGEX.fullmatch(codigo):
            raise ValidationError(
                gettext('Elige un codigo de 4 a 20 letras o numeros (sin espacios ni simbolos) que te represente a ti y a tu marca.')
            )
        if not codigo_referido_disponible(codigo, excluir_profile_pk=self.instance.pk):
            raise ValidationError(gettext('Ese codigo ya esta en uso. Elige otro.'))
        return codigo


def con_puntos_de_mil(numero):
    return f'{numero:,}'.replace(',', '.')


class SeguidoresInput(forms.TextInput):
    """Muestra la cifra con punto de mil (1.000.000) para que se lea de un
    vistazo. Es texto y no `number`: un input numerico no admite los puntos."""

    def format_value(self, value):
        if isinstance(value, int):
            return con_puntos_de_mil(value)
        return super().format_value(value)


class SeguidoresField(forms.IntegerField):
    """Acepta la cifra con o sin puntos de mil ("1.000.000" o "1000000")."""

    def to_python(self, value):
        if isinstance(value, str):
            value = re.sub(r'[.\s]', '', value)
        return super().to_python(value)


class PerfilAfiliadoForm(DatosPersonalesForm):
    """Edicion de los datos personales desde el panel del afiliado."""

    class Meta:
        model = PerfilAfiliado
        fields = list(CAMPOS_PERSONALES)
        labels = ETIQUETAS_PERSONALES


class RedSocialForm(forms.Form):
    platform = forms.ChoiceField(label=gettext_lazy('Red social'), choices=SocialPlatform.choices, initial=SocialPlatform.INSTAGRAM)
    other_name = forms.CharField(
        label=gettext_lazy('Nombre de la red'), max_length=60, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
    )
    username = forms.CharField(
        label=gettext_lazy('Usuario'), max_length=61,
        widget=forms.TextInput(attrs={'placeholder': 'tu_usuario', 'autocomplete': 'off'}),
    )
    followers = SeguidoresField(
        label=gettext_lazy('Seguidores'), min_value=0, max_value=MAX_SEGUIDORES,
        widget=SeguidoresInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off', 'placeholder': '0', 'data-miles': ''}),
        error_messages={'required': gettext_lazy('Indica cuantos seguidores tienes.')},
    )

    def clean_username(self):
        usuario = self.cleaned_data['username'].strip().removeprefix('@')
        if not USUARIO_DE_RED.fullmatch(usuario):
            raise ValidationError(gettext('Escribe solo tu usuario (2 a 60 letras, numeros, punto, guion o guion bajo), sin enlaces ni espacios.'))
        return usuario

    def clean(self):
        datos = super().clean()
        if datos.get('platform') == SocialPlatform.OTHER and not (datos.get('other_name') or '').strip():
            self.add_error('other_name', 'Escribe el nombre de la red.')
        elif datos.get('platform') != SocialPlatform.OTHER:
            datos['other_name'] = ''
        return datos


class BaseRedSocialFormSet(forms.BaseFormSet):
    """Exige al menos una red y no admite la misma red con el mismo usuario
    dos veces: inflaria la audiencia declarada."""

    def clean(self):
        super().clean()
        vistas = set()
        for formulario in self.forms:
            datos = getattr(formulario, 'cleaned_data', None)
            if not datos or 'username' not in datos:
                continue
            clave = (datos['platform'], (datos.get('other_name') or '').lower(), datos['username'].lower())
            if clave in vistas:
                raise ValidationError(gettext('Hay una red repetida: la misma red con el mismo usuario solo se cuenta una vez.'))
            vistas.add(clave)


RedSocialFormSet = forms.formset_factory(
    RedSocialForm, formset=BaseRedSocialFormSet, extra=0, min_num=1, validate_min=True,
    max_num=MAX_REDES, validate_max=True,
)
RedSocialFormSet.default_error_messages = {
    'too_few_forms': gettext_lazy('Agrega al menos una red social.'),
    'too_many_forms': gettext_lazy('Puedes agregar hasta %(max)s redes sociales.') % {'max': MAX_REDES},
    'missing_management_form': gettext_lazy('Faltan datos del formulario de redes sociales. Recarga la pagina e intenta de nuevo.'),
}
