"""Cliente OIDC: Authorization Code + PKCE S256 y validacion del ID token.

No guarda nada en disco ni en la base: el estado del flujo vive en la sesion
(ver views.py) y los metadatos/claves publicas en cache.
"""
import base64
import hashlib
import hmac
import secrets
from urllib.parse import urlencode, urlparse

import jwt
import requests
from django.core.cache import cache

from . import conf


class OIDCError(Exception):
    """Fallo del flujo. El mensaje es un codigo corto, apto para logs."""


def discovery_url():
    return conf.get('DISCOVERY_URL') or conf.get('ISSUER').rstrip('/') + '/.well-known/openid-configuration'


def get_metadata():
    url = discovery_url()
    cache_key = 'gotogym_oidc:metadata:' + hashlib.sha256(url.encode()).hexdigest()
    metadata = cache.get(cache_key)
    if metadata is None:
        response = requests.get(url, timeout=conf.get('HTTP_TIMEOUT_SECONDS'))
        response.raise_for_status()
        metadata = response.json()
        if metadata.get('issuer') != conf.get('ISSUER'):
            raise OIDCError('metadata_issuer_mismatch')
        for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
            if not metadata.get(key):
                raise OIDCError(f'metadata_missing_{key}')
        for field in ('issuer', 'authorization_endpoint', 'token_endpoint', 'jwks_uri', 'end_session_endpoint'):
            endpoint = metadata.get(field)
            if endpoint:
                parsed = urlparse(endpoint)
                if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                    raise OIDCError('metadata_insecure_endpoint')
        cache.set(cache_key, metadata, conf.get('METADATA_TTL_SECONDS'))
    return metadata


def new_flow():
    """Valores de un solo uso para una vuelta al IdP."""
    verifier = secrets.token_urlsafe(64)
    return {
        'state': secrets.token_urlsafe(32),
        'nonce': secrets.token_urlsafe(32),
        'verifier': verifier,
    }


def code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def build_authorization_url(metadata, flow, redirect_uri):
    params = {
        'client_id': conf.get('CLIENT_ID'),
        'response_type': 'code',
        'scope': conf.get('SCOPES'),
        'redirect_uri': redirect_uri,
        'state': flow['state'],
        'nonce': flow['nonce'],
        'code_challenge': code_challenge(flow['verifier']),
        'code_challenge_method': 'S256',
    }
    return metadata['authorization_endpoint'] + '?' + urlencode(params)


def exchange_code(metadata, code, verifier, redirect_uri):
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': conf.get('CLIENT_ID'),
        'code_verifier': verifier,
    }
    if conf.get('CLIENT_SECRET'):
        data['client_secret'] = conf.get('CLIENT_SECRET')
    response = requests.post(metadata['token_endpoint'], data=data, timeout=conf.get('HTTP_TIMEOUT_SECONDS'))
    if response.status_code != 200:
        # Solo el codigo de error del IdP: el cuerpo puede traer datos sensibles.
        try:
            reason = response.json().get('error', 'unknown')
        except ValueError:
            reason = 'unknown'
        raise OIDCError(f'token_endpoint_{response.status_code}_{reason}')
    id_token = response.json().get('id_token')
    if not id_token:
        raise OIDCError('token_response_without_id_token')
    return id_token


_jwk_clients: dict[str, jwt.PyJWKClient] = {}


def get_signing_key(id_token, jwks_uri):
    jwk_client = _jwk_clients.get(jwks_uri)
    if jwk_client is None:
        jwk_client = _jwk_clients[jwks_uri] = jwt.PyJWKClient(
            jwks_uri, cache_keys=True, lifespan=conf.get('METADATA_TTL_SECONDS'),
            timeout=conf.get('HTTP_TIMEOUT_SECONDS'),
        )
    return jwk_client.get_signing_key_from_jwt(id_token).key


def validate_id_token(id_token, nonce, metadata):
    """Verifica firma, emisor, audiencia, vigencia y nonce. Devuelve los claims."""
    algorithms = conf.get('ID_TOKEN_ALGORITHMS')
    try:
        header = jwt.get_unverified_header(id_token)
        if header.get('alg') not in algorithms:
            raise OIDCError('id_token_bad_alg')
        key = get_signing_key(id_token, metadata['jwks_uri'])
        claims = jwt.decode(
            id_token,
            key,
            algorithms=algorithms,
            audience=conf.get('CLIENT_ID'),
            issuer=conf.get('ISSUER'),
            leeway=conf.get('CLOCK_SKEW_SECONDS'),
            options={'require': ['exp', 'iat', 'iss', 'aud']},
        )
    except jwt.PyJWTError as exc:
        raise OIDCError(f'id_token_invalid_{type(exc).__name__}') from exc
    aud = claims.get('aud')
    if (isinstance(aud, list) and len(aud) > 1 and claims.get('azp') != conf.get('CLIENT_ID')) or (claims.get('azp') and claims['azp'] != conf.get('CLIENT_ID')):
        raise OIDCError('id_token_azp_mismatch')
    if not hmac.compare_digest(str(claims.get('nonce', '')), nonce):
        raise OIDCError('id_token_nonce_mismatch')
    return claims


def end_session_url(post_logout_redirect_uri=None):
    """URL para cerrar tambien la sesion del IdP, o None si no lo soporta."""
    endpoint = get_metadata().get('end_session_endpoint')
    if not endpoint:
        return None
    params = {'client_id': conf.get('CLIENT_ID')}
    redirect = post_logout_redirect_uri or conf.get('POST_LOGOUT_REDIRECT_URI')
    if redirect:
        params['post_logout_redirect_uri'] = redirect
    return endpoint + ('&' if '?' in endpoint else '?') + urlencode(params)

