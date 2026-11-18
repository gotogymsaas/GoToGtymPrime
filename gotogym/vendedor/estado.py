"""Estado de identidad comercial en Prime: no expone oid, IDs, PII ni secretos.

El browser recibe un epoch HMAC opaco para distinguir sesiones y permisos.
No confundir la sesión local con el vínculo OIDC verificable de Django.
"""
import hashlib
import hmac
import secrets

from django.conf import settings
from gotogym_oidc.models import ExternalIdentityLink

from .identidad import credencial
from .models import CommercePersonalizationConsent


def estado_usuario(request):
    user = getattr(request, "user", None)
    linked = None
    consent = None
    scopes = []
    issuer = str((getattr(settings, "GOTOGYM_OIDC", {}) or {}).get("ISSUER") or "").strip()
    if user is None or not user.is_authenticated:
        mode = "anonymous"
        identity = "anonymous"
    else:
        linked = (ExternalIdentityLink.objects.filter(user=user, issuer=issuer).first()
                  if issuer else None)
        consent = CommercePersonalizationConsent.objects.filter(user=user).first()
        scopes = consent.active_scopes() if consent else []
        if linked is None:
            mode = "link_required"
        elif not scopes:
            mode = "consent_required"
        elif not (settings.VENDEDOR_CONTRATO_V2 and credencial()):
            mode = "identity_not_ready"
        else:
            mode = "linked"
        identity = f"user:{user.pk}:issuer:{issuer}:oid:{linked.subject if linked else '-'}"
    version = consent.version if consent is not None else 0
    # Cualquier cambio de identidad, versión de consentimiento o scopes activos
    # cambia el epoch. La sesión nunca se identifica por correo ni nombre.
    # Un nonce persistente por sesion es estable desde el primer GET/POST;
    # la session_key puede ser None en el primer turno y cambiar al guardarse.
    # El valor nunca se transmite: solo se expone el HMAC de la vinculacion.
    nonce = request.session.setdefault("_vendedor_epoch_nonce", secrets.token_hex(16))
    private = f"{nonce}|{identity}|{mode}|{version}|{','.join(scopes)}"
    epoch = hmac.new(settings.SECRET_KEY.encode("utf-8"), private.encode("utf-8"),
                     hashlib.sha256).hexdigest()[:32]
    next_step = {
        "anonymous": "continue_general",
        "link_required": "link_account",
        "consent_required": "optional_personalization",
        "identity_not_ready": "continue_general",
        "linked": "ready",
    }[mode]
    return {
        "next_step": next_step,
        "epoch": epoch,
        "mode": mode,
        "personalization_ready": mode == "linked",
        "scope_count": len(scopes),
    }
