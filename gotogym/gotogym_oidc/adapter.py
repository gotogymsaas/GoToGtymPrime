"""Puntos de extension para adaptar el modulo al modelo de usuario de cada app.

Se reemplaza con `GOTOGYM_OIDC['ADAPTER'] = 'miapp.oidc.MiAdapter'`.
"""
import re

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.utils.module_loading import import_string

from . import conf
from .client import OIDCError


def get_adapter():
    return import_string(conf.get('ADAPTER'))()


class DefaultAdapter:
    def validate_claims(self, request, claims):
        """Provider claims never grant local roles; subclasses may gate a canary."""

    def prepare_user(self, request, user, claims):
        """Apply explicit local registration consent to a newly created user only."""

    def validate_user(self, request, user):
        if not user.is_active:
            raise OIDCError('user_inactive')

    def get_email(self, claims):
        email = claims.get('email')
        if not email and isinstance(claims.get('emails'), list) and claims['emails']:
            email = claims['emails'][0]
        if not email and '@' in str(claims.get('preferred_username', '')):
            email = claims['preferred_username']
        return str(email).strip().lower() if email else ''

    def find_user_by_email(self, email):
        matches = list(get_user_model()._default_manager.filter(email__iexact=email)[:2])
        if len(matches) > 1:
            raise OIDCError('ambiguous_local_email')
        return matches[0] if matches else None

    def create_user(self, claims, email):
        """Crea una cuenta local sin contrasena: entra solo por el IdP."""
        User = get_user_model()
        fields = {'email': email}
        for field, claim in (('first_name', 'given_name'), ('last_name', 'family_name')):
            if self._has_field(field) and claims.get(claim):
                fields[field] = str(claims[claim])[:self._max_length(field)]
        if self._has_field('username'):
            fields['username'] = self._unique_username(email)
        user = User(**fields)
        user.set_unusable_password()
        user.save()
        return user

    def post_login_redirect(self, request, user, created, next_url):
        return next_url

    # -- ayudas -----------------------------------------------------------
    def _has_field(self, name):
        try:
            get_user_model()._meta.get_field(name)
            return True
        except FieldDoesNotExist:
            return False

    def _max_length(self, name):
        return get_user_model()._meta.get_field(name).max_length or 150

    def _unique_username(self, email):
        User = get_user_model()
        limit = self._max_length('username')
        base = re.sub(r'[^\w.@+-]', '', email.split('@')[0])[:limit] or 'user'
        candidate, n = base, 1
        while User._default_manager.filter(username__iexact=candidate).exists():
            n += 1
            suffix = f'-{n}'
            candidate = base[:limit - len(suffix)] + suffix
        return candidate


