"""Asercion de identidad de la tienda para el Coach (Identity Bridge).

Le dice al Coach "esta persona es (issuer, oid) y hoy autoriza estos scopes",
para que resuelva su propio `ExternalIdentityLink` y devuelva solo el contexto
consentido. Sin asercion, el Coach atiende en modo anonimo.

Por que una firma aparte de la del paquete:
- Usa su propia credencial (`VENDEDOR_IDENTIDAD_CLAVE_ID/SECRETO`). Quien
  obtenga el secreto del vendedor anonimo puede hablar con el Coach, pero no
  hacerse pasar por un usuario.
- Lleva audiencia, vida de 60 s y un `jti` de un solo uso que el Coach debe
  registrar para rechazar repeticiones.

Nunca se emite por coincidencia de correo: solo con un enlace OIDC verificado
y con al menos un scope activo. El `oid` viaja de servidor a servidor; el
Coach no debe ponerlo en ningun prompt.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

from django.conf import settings
from gotogym_oidc.models import ExternalIdentityLink

from .models import CommercePersonalizationConsent

AUDIENCIA = 'coach-commerce'
EMISOR = 'gotogym-prime'
VIDA_SEGUNDOS = 60
_DOMINIO = b'gotogym-commerce-identity-v1.'


def _b64(datos):
    return base64.urlsafe_b64encode(datos).rstrip(b'=').decode('ascii')


def credencial():
    """`(clave_id, secreto)` o `None` si no esta configurada."""
    clave = getattr(settings, 'VENDEDOR_IDENTIDAD_CLAVE_ID', '') or ''
    secreto = getattr(settings, 'VENDEDOR_IDENTIDAD_SECRETO', '') or ''
    if not clave or not secreto:
        return None
    return clave, secreto


def firmar(secreto, carga_b64):
    return hmac.new(secreto.encode('utf-8'), _DOMINIO + carga_b64.encode('ascii'), hashlib.sha256).hexdigest()


def emitir(user, ahora=None):
    """Bloque `identity` para el paquete v2, o `None` (modo anonimo).

    `None` si: no hay usuario, no hay credencial, la cuenta no esta vinculada
    o no tiene ningun scope vigente. Ninguno de esos casos es un error."""
    if user is None or not user.is_authenticated:
        return None
    par = credencial()
    if par is None:
        return None
    issuer = settings.GOTOGYM_OIDC.get('ISSUER')
    link = ExternalIdentityLink.objects.filter(user=user, issuer=issuer).first() if issuer else None
    if link is None:
        return None
    consent = CommercePersonalizationConsent.objects.filter(user=user).first()
    scopes = consent.active_scopes() if consent else []
    if not scopes:
        return None

    marca = int(time.time() if ahora is None else ahora)
    carga = {
        'iss': EMISOR,
        'aud': AUDIENCIA,
        'idp_issuer': link.issuer,
        'idp_subject': link.subject,
        'scopes': scopes,
        'consent_version': consent.version,
        'iat': marca,
        'exp': marca + VIDA_SEGUNDOS,
        'jti': secrets.token_hex(16),
    }
    carga_b64 = _b64(json.dumps(carga, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    clave_id, secreto = par
    return {
        'key_id': clave_id,
        'assertion': carga_b64,
        'signature': firmar(secreto, carga_b64),
    }


def verificar(secreto, bloque, ahora=None, usados=None):
    """Implementacion de referencia del lado receptor. Devuelve la carga o
    lanza `ValueError` con un codigo corto. `usados` es un conjunto (o algo
    con `add` que devuelva False si ya existia) para el `jti`."""
    if not isinstance(bloque, dict):
        raise ValueError('malformed')
    carga_b64, firma = bloque.get('assertion'), bloque.get('signature')
    if not isinstance(carga_b64, str) or not isinstance(firma, str):
        raise ValueError('malformed')
    if not hmac.compare_digest(firmar(secreto, carga_b64), firma):
        raise ValueError('mismatch')
    relleno = '=' * (-len(carga_b64) % 4)
    try:
        carga = json.loads(base64.urlsafe_b64decode(carga_b64 + relleno))
    except (ValueError, TypeError):
        raise ValueError('malformed') from None
    actual = time.time() if ahora is None else ahora
    if carga.get('aud') != AUDIENCIA or carga.get('iss') != EMISOR:
        raise ValueError('audience')
    if not isinstance(carga.get('exp'), int) or carga['exp'] - carga.get('iat', 0) > VIDA_SEGUNDOS:
        raise ValueError('lifetime')
    if actual >= carga['exp'] or actual < carga.get('iat', 0) - 5:
        raise ValueError('expired')
    if usados is not None:
        jti = carga.get('jti')
        if jti in usados:
            raise ValueError('replay')
        usados.add(jti)
    return carga
