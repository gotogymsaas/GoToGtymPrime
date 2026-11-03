import hashlib
import hmac
import logging
import time
from datetime import timedelta

import requests
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.messages.api import MessageFailure
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import client, conf
from .adapter import get_adapter
from .models import AuthorizationFlow, ExternalIdentityLink

logger = logging.getLogger('gotogym_oidc')

FLOW_KEY = 'gotogym_oidc_flow'
PENDING_KEY = 'gotogym_oidc_pending_link'
# Marca en la sesion de que la persona entro por el IdP (para cerrar sesion alla).
VIA_OIDC_KEY = 'gotogym_oidc_via'


def _safe_next(request, candidate):
    from django.conf import settings
    fallback = resolve_url(settings.LOGIN_REDIRECT_URL or '/')
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def _redirect_uri(request):
    return conf.get('REDIRECT_URI') or request.build_absolute_uri(reverse('gotogym_oidc:callback'))


def _fail(request, reason, user_message='No se pudo iniciar sesion con GoToGym. Intentalo de nuevo.'):
    logger.warning('oidc flow failed: %s', reason)
    from .telemetry import record
    record('authentication', 'failure')
    try:
        messages.error(request, user_message)
    except MessageFailure:
        pass
    from django.conf import settings
    destino = resolve_url(conf.get('ERROR_REDIRECT_URL') or settings.LOGIN_URL)
    # Marca el regreso por error: una pagina de login que redirige sola al IdP
    # debe mostrarse tal cual aqui, o el fallo se volveria un bucle.
    public_reasons = {'identity_terms_required', 'local_mfa_use_password_login', 'identity_canary_not_allowed', 'client_secret_unavailable'}
    suffix = '&identity_error=' + reason if reason in public_reasons else ''
    return redirect(destino + ('&' if '?' in destino else '?') + 'oidc_error=1' + suffix)


@never_cache
@require_GET
def start(request):
    if not conf.get('ENABLED'):
        return HttpResponseNotFound()
    try:
        metadata = client.get_metadata()
    except (requests.RequestException, client.OIDCError, ValueError) as exc:
        return _fail(request, f'metadata_unavailable:{type(exc).__name__}')
    flow = client.new_flow()
    flow['next'] = _safe_next(request, request.GET.get('next'))
    flow['created'] = time.time()
    AuthorizationFlow.objects.filter(expires_at__lt=timezone.now()).delete()
    AuthorizationFlow.objects.create(digest=hashlib.sha256(flow['state'].encode()).hexdigest(), expires_at=timezone.now() + timedelta(seconds=conf.get('FLOW_TTL_SECONDS')))
    request.session[FLOW_KEY] = flow
    return redirect(client.build_authorization_url(metadata, flow, _redirect_uri(request)))


@never_cache
@require_GET
def callback(request):
    if not conf.get('ENABLED'):
        return HttpResponseNotFound()
    # Se consume siempre, incluso si algo falla: el flujo es de un solo uso.
    flow = request.session.pop(FLOW_KEY, None)
    if not flow or time.time() - flow.get('created', 0) > conf.get('FLOW_TTL_SECONDS'):
        return _fail(request, 'flow_missing_or_expired')
    if request.GET.get('error'):
        error = request.GET['error']
        error = error if error in {'access_denied', 'server_error', 'temporarily_unavailable'} else 'provider_error'
        return _fail(request, 'idp_error:' + error)
    if not hmac.compare_digest(request.GET.get('state', ''), flow['state']):
        return _fail(request, 'state_mismatch')
    deleted, _ = AuthorizationFlow.objects.filter(digest=hashlib.sha256(flow['state'].encode()).hexdigest(), expires_at__gt=timezone.now()).delete()
    if deleted != 1:
        return _fail(request, 'flow_already_consumed')
    code = request.GET.get('code')
    if not code:
        return _fail(request, 'missing_code')
    try:
        metadata = client.get_metadata()
        id_token = client.exchange_code(metadata, code, flow['verifier'], _redirect_uri(request))
        claims = client.validate_id_token(id_token, flow['nonce'], metadata)
    except client.OIDCError as exc:
        return _fail(request, str(exc))
    except (requests.RequestException, ValueError) as exc:
        return _fail(request, f'idp_unreachable:{type(exc).__name__}')
    try:
        return _complete_login(request, claims, flow['next'])
    except client.OIDCError as exc:
        return _fail(request, str(exc))


def _complete_login(request, claims, next_url):
    issuer = conf.get('ISSUER')
    subject = claims.get(conf.get('SUBJECT_CLAIM'))
    if not subject:
        return _fail(request, 'subject_claim_missing')
    verified = claims.get('email_verified')
    if (verified is not None and verified is not True) or (verified is None and conf.get('REQUIRE_EMAIL_VERIFIED_CLAIM')):
        return _fail(request, 'email_not_verified')

    adapter = get_adapter()
    adapter.validate_claims(request, claims)
    link = ExternalIdentityLink.objects.select_related('user').filter(issuer=issuer, subject=str(subject)).first()
    if link:
        if not link.user.is_active:
            return _fail(request, 'user_inactive')
        return _finish(request, adapter, link.user, link, False, next_url)

    email = adapter.get_email(claims)
    if not email:
        return _fail(request, 'email_claim_missing')
    existing = adapter.find_user_by_email(email)
    if existing is not None:
        # Mismo correo no significa misma persona: se pide la clave local.
        request.session[PENDING_KEY] = {
            'issuer': issuer, 'subject': str(subject), 'email': email,
            'next': next_url, 'created': time.time(),
        }
        return redirect('gotogym_oidc:link')
    if not conf.get('ALLOW_AUTO_CREATE'):
        return _fail(request, 'auto_create_disabled')
    try:
        with transaction.atomic():
            user = adapter.create_user(claims, email)
            adapter.validate_user(request, user)
            adapter.prepare_user(request, user, claims)
            link = ExternalIdentityLink.objects.create(
                user=user, issuer=issuer, subject=str(subject), email_at_link=email,
            )
    except IntegrityError:
        return _fail(request, 'identity_conflict')
    return _finish(request, adapter, user, link, True, next_url)


def _finish(request, adapter, user, link, created, next_url):
    adapter.validate_user(request, user)
    login(request, user, backend=conf.get('AUTH_BACKEND'))
    request.session[VIA_OIDC_KEY] = True
    ExternalIdentityLink.objects.filter(pk=link.pk).update(last_login_at=timezone.now())
    from .telemetry import record
    record('authentication', 'success')
    target = adapter.post_login_redirect(request, user, created, _safe_next(request, next_url))
    return HttpResponseRedirect(target)


def _attempts_key(user):
    return f'gotogym_oidc:link_attempts:{user.pk}'


@never_cache
@csrf_protect
@require_http_methods(['GET', 'POST'])
def link_account(request):
    if not conf.get('ENABLED'):
        return HttpResponseNotFound()
    """Vincula una identidad del IdP con una cuenta local existente (mismo correo)."""
    pending = request.session.get(PENDING_KEY)
    if not pending or time.time() - pending.get('created', 0) > conf.get('FLOW_TTL_SECONDS'):
        request.session.pop(PENDING_KEY, None)
        return _fail(request, 'pending_missing_or_expired')
    adapter = get_adapter()
    try:
        user = adapter.find_user_by_email(pending['email'])
    except client.OIDCError as exc:
        request.session.pop(PENDING_KEY, None)
        return _fail(request, str(exc))
    if user is None or not user.is_active:
        request.session.pop(PENDING_KEY, None)
        return _fail(request, 'link_target_unavailable')

    error = None
    if request.method == 'POST':
        key = _attempts_key(user)
        cache.add(key, 0, conf.get('LINK_ATTEMPTS_WINDOW_SECONDS'))
        if cache.get(key, 0) >= conf.get('LINK_MAX_ATTEMPTS'):
            request.session.pop(PENDING_KEY, None)
            return _fail(request, 'link_too_many_attempts', 'Demasiados intentos. Intentalo mas tarde.')
        if user.check_password(request.POST.get('password', '')):
            try:
                adapter.validate_user(request, user)
            except client.OIDCError as exc:
                return _fail(request, str(exc))
            try:
                with transaction.atomic():
                    link = ExternalIdentityLink.objects.create(
                        user=user, issuer=pending['issuer'], subject=pending['subject'],
                        email_at_link=pending['email'],
                    )
            except IntegrityError:
                request.session.pop(PENDING_KEY, None)
                return _fail(request, 'identity_conflict')
            cache.delete(key)
            request.session.pop(PENDING_KEY, None)
            try:
                return _finish(request, adapter, user, link, False, pending['next'])
            except client.OIDCError as exc:
                return _fail(request, str(exc))
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, conf.get('LINK_ATTEMPTS_WINDOW_SECONDS'))
        error = 'Contrasena incorrecta.'
    return render(request, 'gotogym_oidc/link_account.html', {'email': pending['email'], 'error': error})


@never_cache
@require_POST
@csrf_protect
def logout_view(request):
    """Cierra la sesion local y, si la persona entro por el IdP, tambien la de alla."""
    via_oidc = request.session.get(VIA_OIDC_KEY)
    logout(request)
    if via_oidc:
        try:
            url = client.end_session_url()
        except (requests.RequestException, client.OIDCError, ValueError):
            url = None
        if url:
            return redirect(url)
    from django.conf import settings
    return redirect(_safe_next(request, request.POST.get('next')) or settings.LOGIN_URL)


