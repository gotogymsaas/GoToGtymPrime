"""Reglas de contrasena de la tienda.

Son pocas y faciles de explicar a quien se registra: 8 caracteres o mas, con
mayuscula, minuscula, numero y un caracter especial. El mismo validador
protege el registro, el cambio de contrasena del perfil y el restablecimiento
por correo.
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

LARGO_MINIMO = 8

REGLAS_TEXTO = _(
    'Mínimo 8 caracteres, con una mayúscula, una minúscula, un número y un carácter especial (por ejemplo ! ? # $ @).'
)


class ContrasenaSegura:
    """Exige largo minimo y los cuatro tipos de caracter."""

    def validate(self, password, user=None):
        faltantes = []
        if len(password) < LARGO_MINIMO:
            faltantes.append(_('al menos 8 caracteres'))
        if not any(c.isupper() for c in password):
            faltantes.append(_('una mayúscula'))
        if not any(c.islower() for c in password):
            faltantes.append(_('una minúscula'))
        if not any(c.isdigit() for c in password):
            faltantes.append(_('un número'))
        if not any(not c.isalnum() and not c.isspace() for c in password):
            faltantes.append(_('un carácter especial (por ejemplo ! ? # $ @)'))
        if faltantes:
            raise ValidationError(
                _('La contraseña debe tener %(faltantes)s.') % {'faltantes': ', '.join(str(f) for f in faltantes)},
                code='contrasena_insegura',
            )

    def get_help_text(self):
        return REGLAS_TEXTO
