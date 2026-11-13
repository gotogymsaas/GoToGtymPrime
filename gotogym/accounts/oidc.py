"""Entrada con la cuenta GoToGym (OIDC): adaptacion del modulo compartido
`gotogym_oidc` a la tienda.

Quien entra por primera vez con GoToGym no paso por el formulario de registro
de la tienda, asi que aun no acepto sus terminos: se le piden justo despues de
entrar (`accept_terms`) y antes de seguir a donde iba."""
import hashlib
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext
from django.views.decorators.csrf import csrf_protect
from gotogym_oidc import conf
from gotogym_oidc.adapter import DefaultAdapter
from gotogym_oidc.client import OIDCError

from .signals import perfil_creado
from .views import TERMS_PATH


class PrimeAdapter(DefaultAdapter):
    def validate_claims(self, request, claims):
        """Mientras el inicio de sesion no este abierto a todos, solo entra quien
        figura en la lista del canary. Se comprueba antes de buscar el vinculo o
        la cuenta, de modo que una identidad fuera de la lista no toca ninguna
        cuenta, ni siquiera una ya vinculada."""
        if getattr(settings, 'OIDC_GLOBAL', False):
            return
        subject = claims.get(conf.get('SUBJECT_CLAIM'))
        if not subject or str(subject) not in getattr(settings, 'OIDC_CANARY_OBJECT_IDS', frozenset()):
            raise OIDCError('canary_not_allowed')

    def post_login_redirect(self, request, user, created, next_url):
        if user.accepted_terms:
            return next_url
        return reverse('accept_terms') + '?' + urlencode({'next': next_url})


def oidc_habilitado(request):
    """Context processor: la plantilla muestra "Continuar con GoToGym" solo si
    el inicio de sesion unificado esta abierto a todos. En el canary el boton
    queda oculto y quien prueba lo ve con `?sso=1`."""
    solicitada_prueba = request.GET.get('sso') == '1'
    visible = settings.OIDC_HABILITADO and (
        getattr(settings, 'OIDC_GLOBAL', False) or solicitada_prueba
    )
    # ?sso=1 muestra el enlace SOLO si el servidor habilito OIDC.
    # Cuando no esta disponible, explicar la situacion sin simular
    # un inicio de sesion ni revelar secretos o ajustes internos.
    return {
        'oidc_habilitado': visible,
        'oidc_prueba_no_disponible': solicitada_prueba and not settings.OIDC_HABILITADO,
    }


@login_required
@csrf_protect
def accept_terms(request):
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse('home')
    if request.user.accepted_terms:
        return redirect(next_url)
    if request.method == 'POST':
        if request.POST.get('accepted_terms'):
            terms_text = TERMS_PATH.read_text(encoding='utf-8')
            user = request.user
            user.accepted_terms = True
            user.terms_accepted_at = timezone.now()
            user.terms_hash = hashlib.sha512(terms_text.encode()).hexdigest()
            user.save(update_fields=['accepted_terms', 'terms_accepted_at', 'terms_hash'])
            perfil_creado.send(sender=type(user), user=user)
            return redirect(next_url)
        messages.error(request, gettext('Para continuar debes aceptar los términos y condiciones.'))
    return render(request, 'accounts/accept_terms.html', {'next': next_url})

class RequireOIDCTermsMiddleware:
    """A first OIDC login must not bypass terms by navigating away from the form."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        from gotogym_oidc.views import VIA_OIDC_KEY
        if not request.user.is_authenticated or not request.session.get(VIA_OIDC_KEY) or request.user.accepted_terms:
            return None
        match = request.resolver_match
        if match and (match.url_name in {'accept_terms', 'logout'} or match.namespace == 'gotogym_oidc'):
            return None
        if request.path.startswith((settings.STATIC_URL, settings.MEDIA_URL)):
            return None
        return redirect(reverse('accept_terms') + '?' + urlencode({'next': request.get_full_path()}))
