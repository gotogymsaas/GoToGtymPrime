"""Consulta y revocación de personalización comercial del titular.

M14: no exporta identidad OIDC, medidas corporales, mensajes ni datos de otro
usuario. Mantiene la evidencia de las decisiones; no es un ledger jurídico
interoperable entre APP y Shop ni modifica condiciones contractuales.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from . import consentimiento
from .models import (
    SCOPE_FIELDS,
    CommerceConsentAuditEvent,
    CommerceMemoryItem,
    CommercePersonalizationConsent,
    TailoringMeasurement,
)

MAX_EVENTS = 100


@never_cache
@login_required
@require_GET
def recibo(request):
    """Recibo privado de permisos propios: no equivale a aprobar otra finalidad."""
    now = timezone.now()
    row = CommercePersonalizationConsent.objects.filter(user=request.user).first()
    audit = CommerceConsentAuditEvent.objects.filter(user=request.user)
    latest = list(audit.order_by("-pk").values(
        "scope", "allowed", "consent_version", "created_at")[:MAX_EVENTS])
    response = JsonResponse({
        "schema_version": 1,
        "product": "gotogym_shop",
        "purpose": "commerce_personalization",
        "current": consentimiento._projection(row, now),
        "recent_decisions": latest,
        "decision_count": audit.count(),
        "recent_limit": MAX_EVENTS,
        "data_categories": {
            "measurements_recorded": TailoringMeasurement.objects.filter(user=request.user).exists(),
            "commercial_memory_recorded": CommerceMemoryItem.objects.filter(user=request.user).exists(),
        },
        "legal_equivalence_to_other_products": False,
    })
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@csrf_protect
@login_required
@require_POST
def revocar_todo(request):
    """Revoca todos los scopes opcionales, sin tocar cuenta, órdenes o planes.

    Confirmación explícita de formulario; no se procesa en GET. Nunca se borra
    el rastro mínimo de auditoría de las decisiones de consentimiento.
    """
    if request.POST.get("confirm") != "REVOCAR_PERSONALIZACION":
        return JsonResponse({"error": "confirmation_required"}, status=400)
    with transaction.atomic():
        for scope in SCOPE_FIELDS:
            consentimiento.aplicar(request.user, scope, False)
        # Limpia incluso datos huérfanos previos o permisos ya caducados.
        TailoringMeasurement.objects.filter(user=request.user).delete()
        CommerceMemoryItem.objects.filter(user=request.user).delete()
    messages.success(request, _("Se desactivó la personalización comercial opcional."))
    response = redirect(reverse("edit_profile") + "#personalizacion")
    response["Cache-Control"] = "no-store"
    return response
