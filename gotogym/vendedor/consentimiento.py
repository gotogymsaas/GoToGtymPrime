"""Consentimiento granular del vendedor. No lee datos del Coach.

Al crear el perfil (aceptar por primera vez los terminos de la tienda, que
informan esta finalidad) la personalizacion queda activada en todos sus
scopes: es la autorizacion dada en el registro (`conceder_al_crear_perfil`).
Despues, conceder a mano exige el enlace OIDC, que NO es consentimiento.
En ambos casos los datos del Coach solo viajan con la cuenta vinculada (la
asercion de identidad lo exige). Revocar no exige enlace: un permiso siempre
se puede retirar, aunque la cuenta se haya desvinculado despues.
Los endpoints son same-origin; POST utiliza CSRF y sesion Django.
"""
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from gotogym_oidc.models import ExternalIdentityLink

from .models import (
    CONSENT_VALIDITY,
    SCOPE_FIELDS,
    CommerceConsentAuditEvent,
    CommerceMemoryItem,
    CommercePersonalizationConsent,
    TailoringMeasurement,
)

SCOPES = SCOPE_FIELDS
MAX_BODY_BYTES = 1024


def _response(payload, status=200):
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _projection(consent, now=None):
    now = now or timezone.now()
    scopes, expires = {}, {}
    for scope in SCOPES:
        active = consent is not None and consent.is_active(scope, now)
        scopes[scope] = active
        if active:
            granted = timezone.datetime.fromisoformat(consent.granted_at[scope])
            expires[scope] = (granted + CONSENT_VALIDITY).isoformat()
    return {
        "version": consent.version if consent is not None else 0,
        "scopes": scopes,
        "expires_at": expires,
    }


def _read_body(request):
    """`(data, None)` o `(None, respuesta_de_error)`."""
    try:
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return None, _response({"error": "invalid_request"}, 400)
    if declared > MAX_BODY_BYTES or len(request.body) > MAX_BODY_BYTES:
        return None, _response({"error": "invalid_request"}, 413)
    if request.content_type != "application/json":
        return None, _response({"error": "invalid_request"}, 415)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, _response({"error": "invalid_request"}, 400)
    if (not isinstance(data, dict) or set(data) != {"scope", "allowed"}
            or data.get("scope") not in SCOPES or type(data.get("allowed")) is not bool):
        return None, _response({"error": "invalid_scope"}, 400)
    return data, None


@never_cache
@csrf_protect
@login_required
@require_http_methods(["GET", "POST"])
def consentimiento(request):
    # Nunca se autoriza personalizar por mera coincidencia de correo.
    linked = ExternalIdentityLink.objects.filter(user=request.user).exists()

    if request.method == "GET":
        row = CommercePersonalizationConsent.objects.filter(user=request.user).first()
        return _response({"linked": linked, **_projection(row)}, 200 if linked or row else 403)

    data, error = _read_body(request)
    if error is not None:
        return error
    scope, allowed = data["scope"], data["allowed"]
    if allowed and not linked:
        return _response({"linked": False, **_projection(None)}, 403)
    now = timezone.now()
    row = aplicar(request.user, scope, allowed, now)
    return _response({"linked": linked, **_projection(row, now)})


def aplicar(user, scope, allowed, now=None):
    """Concede o revoca un scope y devuelve la fila (o None si no habia nada
    que revocar). Quien llama ya comprobo el enlace para conceder.

    Revocar borra los datos que solo existian por ese permiso: las medidas y
    la memoria comercial no sobreviven a su consentimiento."""
    now = now or timezone.now()
    with transaction.atomic():
        if allowed:
            row, _ = CommercePersonalizationConsent.objects.select_for_update().get_or_create(user=user)
        else:
            row = CommercePersonalizationConsent.objects.select_for_update().filter(user=user).first()
        if not allowed:
            _borrar_datos_del_scope(user, scope)
        if row is None:
            return None
        field = SCOPES[scope]
        # Conceder renueva un permiso caducado; revocar apaga aunque ya hubiera caducado.
        changed = (not row.is_active(scope, now)) if allowed else getattr(row, field)
        if changed:
            setattr(row, field, allowed)
            granted = dict(row.granted_at or {})
            if allowed:
                granted[scope] = now.isoformat()
            else:
                granted.pop(scope, None)
            row.granted_at = granted
            row.version += 1
            row.save(update_fields=[field, "granted_at", "version", "updated_at"])
            CommerceConsentAuditEvent.objects.create(
                user=user, scope=scope, allowed=allowed, consent_version=row.version,
            )
    return row


def conceder_al_crear_perfil(user, now=None):
    """Activa todos los scopes para quien acaba de crear su perfil.

    Solo si nunca hubo una decision suya (no existe fila): no reactiva algo
    que la persona apago. Cada scope queda auditado como cualquier concesion."""
    if CommercePersonalizationConsent.objects.filter(user=user).exists():
        return None
    now = now or timezone.now()
    row = None
    for scope in SCOPES:
        row = aplicar(user, scope, True, now)
    return row


def al_crear_perfil(sender, user, **kwargs):
    """Receptor de `accounts.signals.perfil_creado` (ver apps.py)."""
    conceder_al_crear_perfil(user)


def _borrar_datos_del_scope(user, scope):
    if scope == "tailoring.measurements":
        TailoringMeasurement.objects.filter(user=user).delete()
    elif scope == "conversation.commerce_memory":
        CommerceMemoryItem.objects.filter(user=user).delete()
