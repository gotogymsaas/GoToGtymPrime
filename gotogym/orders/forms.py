"""Formulario de checkout: datos de contacto y de entrega.

La validacion vive aqui, no en los atributos HTML: el navegador puede
saltarselos y la peticion puede llegar sin pasar por el formulario.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django import forms
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from . import tarjetas_regalo
from .colombia_data import DEPARTAMENTOS, municipios_de
from .documentos import error_de_documento, limpiar_numero
from .models import DocumentType
from .services import es_cupon_propio, get_usable_coupon


def error_de_tarjeta(codigo, user):
    """Mensaje para un codigo de tarjeta de regalo que no se puede usar, o
    vacio si se puede. Cada codigo equivocado cuenta para el tope de intentos
    de la cuenta (ver `tarjetas_regalo.demasiados_intentos`)."""
    if tarjetas_regalo.demasiados_intentos(user):
        return gettext('Hiciste demasiados intentos con códigos de tarjeta. Inténtalo de nuevo en una hora.')
    tarjeta = tarjetas_regalo.buscar_por_codigo(codigo)
    if tarjeta is None:
        tarjetas_regalo.registrar_intento_fallido(user)
        return gettext('La tarjeta de regalo no es válida.')
    if tarjeta.is_usable():
        return ''
    motivo = tarjetas_regalo.motivo_no_usable(tarjeta)
    if motivo == 'expired':
        return gettext('La tarjeta de regalo venció el %(fecha)s.') % {
            'fecha': date_format(timezone.localtime(tarjeta.expires_at), 'DATE_FORMAT')}
    if motivo == 'no_balance':
        return gettext('La tarjeta de regalo ya no tiene saldo.')
    return gettext('La tarjeta de regalo no está disponible.')


def parece_tarjeta(codigo):
    """Si el codigo tiene la forma de una tarjeta de regalo (16 caracteres
    sin contar guiones). Un codigo asi que no existe cuenta como intento
    fallido aunque se haya escrito como cupon: si no, el campo unico serviria
    para probar codigos de tarjeta sin tope."""
    return len(tarjetas_regalo.normalizar_codigo(codigo)) == tarjetas_regalo.LARGO_CODIGO


def clasificar_codigo(codigo, user):
    """Que es un codigo escrito en el campo "Cupon o tarjeta de regalo".

    Devuelve `('tarjeta', GiftCard)` si es una tarjeta (usable o no),
    `('bloqueado', None)` si la cuenta agoto sus intentos y el codigo tiene
    forma de tarjeta, o `('cupon', None)` en cualquier otro caso: quien llama
    lo valida como cupon. No cuenta intentos: eso lo hace quien sabe que el
    codigo tampoco era un cupon valido."""
    if parece_tarjeta(codigo):
        if tarjetas_regalo.demasiados_intentos(user):
            return 'bloqueado', None
        tarjeta = tarjetas_regalo.buscar_por_codigo(codigo)
        if tarjeta is not None:
            return 'tarjeta', tarjeta
    return 'cupon', None


MENSAJE_DEMASIADOS_INTENTOS = _('Hiciste demasiados intentos con códigos de tarjeta. Inténtalo de nuevo en una hora.')

TELEFONO_VALIDO = re.compile(r'^[0-9+()\s-]{7,20}$')


class CheckoutForm(forms.Form):
    first_name = forms.CharField(label=_('Nombre'), max_length=100)
    last_name = forms.CharField(label=_('Apellido'), max_length=100)
    # Identificacion para la factura electronica. Opcional: sin ella la
    # factura sale a nombre de consumidor final, si la tienda lo tiene
    # configurado. Va justo debajo del nombre porque es de la misma persona.
    document_type = forms.ChoiceField(
        label=_('Tipo de documento'), required=False,
        choices=[('', _('Selecciona un tipo'))] + list(DocumentType.choices),
    )
    document_number = forms.CharField(label=_('Número de documento'), max_length=20, required=False)
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
    # Campo unico "Cupon o tarjeta de regalo": lo que se escribe aqui se
    # reparte en `coupon_code` o `gift_card_code` (ver `clean`). Esos dos
    # viajan ocultos con lo ya aplicado, para poder combinar un cupon y una
    # tarjeta en el mismo pedido.
    discount_code = forms.CharField(label=_('Cupón o tarjeta de regalo'), required=False, max_length=30)
    coupon_code = forms.CharField(label=_('Cupón'), required=False, max_length=30)
    # Admite el codigo con guiones o espacios (XXXX-XXXX-XXXX-XXXX).
    gift_card_code = forms.CharField(label=_('Tarjeta de regalo'), required=False, max_length=24)

    def __init__(self, *args, user=None, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not TELEFONO_VALIDO.match(phone):
            raise forms.ValidationError(
                gettext('Escribe un teléfono válido: entre 7 y 20 caracteres, solo números y + ( ) - espacios.')
            )
        return phone

    def clean_document_number(self):
        return limpiar_numero(self.data.get('document_type'), self.cleaned_data['document_number'])

    def clean_first_name(self):
        return self._texto_no_vacio('first_name', 'Escribe tu nombre.')

    def clean_last_name(self):
        return self._texto_no_vacio('last_name', 'Escribe tu apellido.')

    def clean_address_line(self):
        direccion = self.cleaned_data['address_line'].strip()
        if len(direccion) < 5:
            raise forms.ValidationError(gettext('La dirección es demasiado corta.'))
        return direccion

    def _repartir_codigo(self, cleaned_data):
        """Lleva lo escrito en el campo unico a `coupon_code` o a
        `gift_card_code`. Un pedido admite un cupon y una tarjeta."""
        codigo = (cleaned_data.get('discount_code') or '').strip()
        if not codigo:
            return
        tipo, _tarjeta = clasificar_codigo(codigo, self._user)
        if tipo == 'bloqueado':
            self.add_error('discount_code', str(MENSAJE_DEMASIADOS_INTENTOS))
            return
        campo = 'gift_card_code' if tipo == 'tarjeta' else 'coupon_code'
        nuevo = tarjetas_regalo.normalizar_codigo(codigo) if tipo == 'tarjeta' else codigo.upper()
        anterior = (cleaned_data.get(campo) or '').strip()
        if tipo == 'tarjeta':
            anterior = tarjetas_regalo.normalizar_codigo(anterior)
        if anterior and anterior != nuevo.upper():
            self.add_error('discount_code', gettext(
                'Solo puedes usar una tarjeta de regalo por pedido.' if tipo == 'tarjeta'
                else 'Ya aplicaste un cupón: quítalo para usar otro.'
            ))
            return
        cleaned_data[campo] = nuevo

    def clean(self):
        cleaned_data: dict[str, Any] = super().clean()  # type: ignore[assignment]
        self._repartir_codigo(cleaned_data)
        codigo_cupon = (cleaned_data.get('coupon_code') or '').strip().upper()
        if codigo_cupon and get_usable_coupon(codigo_cupon, user=self._user) is None:
            if es_cupon_propio(codigo_cupon, self._user):
                self.add_error('coupon_code', 'No puedes usar tu propio código de afiliado en tus compras.')
            else:
                if parece_tarjeta(codigo_cupon):
                    tarjetas_regalo.registrar_intento_fallido(self._user)
                self.add_error('coupon_code', gettext('El código no es válido.'))
        cleaned_data['coupon_code'] = codigo_cupon
        codigo_tarjeta = tarjetas_regalo.normalizar_codigo(cleaned_data.get('gift_card_code', ''))
        if codigo_tarjeta:
            error = error_de_tarjeta(codigo_tarjeta, self._user)
            if error:
                self.add_error('gift_card_code', error)
        cleaned_data['gift_card_code'] = codigo_tarjeta
        self._validar_documento(cleaned_data)
        departamento = cleaned_data.get('department')
        ciudad = cleaned_data.get('city', '').strip()
        if departamento and ciudad and ciudad not in municipios_de(departamento):
            self.add_error(
                'city',
                'Selecciona una ciudad válida para el departamento elegido.',
            )
        cleaned_data['city'] = ciudad
        return cleaned_data

    def _validar_documento(self, cleaned_data):
        if 'document_type' in self.errors or 'document_number' in self.errors:
            return
        error = error_de_documento(
            cleaned_data.get('document_type', ''), cleaned_data.get('document_number', ''),
        )
        if error:
            self.add_error(*error)

    def _texto_no_vacio(self, campo, mensaje):
        valor = self.cleaned_data[campo].strip()
        if not valor:
            raise forms.ValidationError(mensaje)
        return valor


# Un enlace en la dedicatoria saldria en un correo con el dominio de GoToGym:
# se rechaza para que la tarjeta no sirva para enviar enlaces enganosos.
PARECE_ENLACE = re.compile(r'https?://|www\.|\b[\w-]+\.(com|co|net|org|io|ly|me|info|xyz|link|app)\b', re.IGNORECASE)


class GiftCardPurchaseForm(forms.Form):
    """Compra de una tarjeta de regalo: valor, para quien es y la dedicatoria.

    El valor llega como texto para aceptar "100.000" o "$100,000": se limpia
    y se valida contra el rango en el servidor, nunca solo en el navegador."""

    amount = forms.CharField(label=_('Valor de la tarjeta'), max_length=20)
    sender_name = forms.CharField(label=_('De parte de'), max_length=80)
    recipient_name = forms.CharField(label=_('Para'), max_length=80)
    recipient_email = forms.EmailField(label=_('Correo de quien recibe el regalo'))
    recipient_email_confirm = forms.EmailField(label=_('Confirma el correo'))
    message = forms.CharField(
        label=_('Dedicatoria (opcional)'), required=False, max_length=tarjetas_regalo.LARGO_DEDICATORIA,
        widget=forms.Textarea(attrs={'rows': 4, 'maxlength': tarjetas_regalo.LARGO_DEDICATORIA}),
    )
    accept_conditions = forms.BooleanField(
        label=_('Acepto las condiciones de la tarjeta de regalo'),
        error_messages={'required': _('Debes aceptar las condiciones de la tarjeta de regalo.')},
    )

    def clean_amount(self):
        texto = re.sub(r'[^\d]', '', self.cleaned_data['amount'] or '')
        try:
            valor = Decimal(texto)
        except InvalidOperation:
            valor = None
        minimo, maximo = tarjetas_regalo.VALOR_MINIMO, tarjetas_regalo.VALOR_MAXIMO
        if valor is None or not minimo <= valor <= maximo:
            raise forms.ValidationError(gettext(
                'Elige un valor entre $%(minimo)s y $%(maximo)s.'
            ) % {'minimo': _miles(minimo), 'maximo': _miles(maximo)})
        return valor

    def clean_sender_name(self):
        return self._texto_sin_enlaces('sender_name', gettext('Escribe tu nombre.'))

    def clean_recipient_name(self):
        return self._texto_sin_enlaces('recipient_name', gettext('Escribe el nombre de quien recibe el regalo.'))

    def clean_recipient_email(self):
        return self.cleaned_data['recipient_email'].strip().lower()

    def clean_recipient_email_confirm(self):
        return self.cleaned_data['recipient_email_confirm'].strip().lower()

    def clean_message(self):
        mensaje = (self.cleaned_data.get('message') or '').strip()
        if PARECE_ENLACE.search(mensaje):
            raise forms.ValidationError(gettext('La dedicatoria no puede incluir enlaces ni direcciones web.'))
        return mensaje

    def clean(self):
        cleaned_data: dict[str, Any] = super().clean()  # type: ignore[assignment]
        correo, confirmacion = cleaned_data.get('recipient_email'), cleaned_data.get('recipient_email_confirm')
        if correo and confirmacion and correo != confirmacion:
            self.add_error('recipient_email_confirm', gettext('Los correos no coinciden.'))
        return cleaned_data

    def _texto_sin_enlaces(self, campo, mensaje_vacio):
        valor = ' '.join((self.cleaned_data.get(campo) or '').split())
        if not valor:
            raise forms.ValidationError(mensaje_vacio)
        if PARECE_ENLACE.search(valor):
            raise forms.ValidationError(gettext('Este campo no puede incluir enlaces.'))
        return valor


def _miles(valor):
    """50000 -> 50.000"""
    return f'{int(valor):,}'.replace(',', '.')
