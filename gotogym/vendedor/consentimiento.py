"""Consentimiento granular del vendedor. No lee datos del Coach.

El enlace OIDC es condicion necesaria pero NO es consentimiento.
Los endpoints son same-origin; POST utiliza CSRF y sesion Django.
"""
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from gotogym_oidc.models import ExternalIdentityLink

from .models import CommerceConsentAuditEvent, CommercePersonalizationConsent

SCOPES = {
    "profile.basic": "profile_basic",
    "sports.preferences": "sports_preferences",
    "experiences.summary": "experiences_summary",
    "tailoring.measurements": "tailoring_measurements",
}
MAX_BODY_BYTES = 1024


def _response(payload, status=200):
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _projection(consent):
    return {
        "version": consent.version if consent is not None else 0,
        "scopes": {
            scope: bool(getattr(consent, field)) if consent is not None else False
            for scope, field in SCOPES.items()
        },
    }


@never_cache
@csrf_protect
@login_required
@require_http_methods(["GET", "POST"])
def consentimiento(request):
    # Nunca se autoriza personalizar por mera coincidencia de correo.
    if not ExternalIdentityLink.objects.filter(user=request.user).exists():
        return _response({"linked": False, **_projection(None)}, 403)

    if request.method == "GET":
        row = CommercePersonalizationConsent.objects.filter(user=request.user).first()
        return _response({"linked": True, **_projection(row)})

    try:
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return _response({"error": "invalid_request"}, 400)
    if declared > MAX_BODY_BYTES or len(request.body) > MAX_BODY_BYTES:
        return _response({"error": "invalid_request"}, 413)
    if request.content_type != "application/json":
        return _response({"error": "invalid_request"}, 415)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _response({"error": "invalid_request"}, 400)
    if (not isinstance(data, dict) or set(data) != {"scope", "allowed"}
            or data.get("scope") not in SCOPES or type(data.get("allowed")) is not bool):
        return _response({"error": "invalid_scope"}, 400)

    scope, allowed = data["scope"], data["allowed"]
    with transaction.atomic():
        row, _ = CommercePersonalizationConsent.objects.select_for_update().get_or_create(
            user=request.user,
        )
        field = SCOPES[scope]
        if getattr(row, field) != allowed:
            setattr(row, field, allowed)
            row.version += 1
            row.save(update_fields=[field, "version", "updated_at"])
            CommerceConsentAuditEvent.objects.create(
                user=request.user, scope=scope, allowed=allowed, consent_version=row.version,
            )
    return _response({"linked": True, **_projection(row)})
