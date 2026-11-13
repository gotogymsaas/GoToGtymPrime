"""Gestion de la personalizacion con Quantum Coach desde Mi cuenta.

Formularios normales (POST + redireccion), sin depender de JavaScript. Cada
cambio pasa por `consentimiento.aplicar`, la misma via que la API JSON, para
que la auditoria y el borrado al revocar sean identicos.
"""
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from gotogym_oidc.models import ExternalIdentityLink
from products.models import ProductVariant

from . import consentimiento
from .models import (
    CONSENT_VALIDITY,
    MEASUREMENT_FIELDS,
    MEMORY_KINDS,
    MEMORY_TTL,
    SCOPE_FIELDS,
    CommerceMemoryItem,
    CommercePersonalizationConsent,
    TailoringMeasurement,
)

# Orden y textos que ve el cliente.
SCOPES_VISIBLES = (
    ("profile.basic", gettext_lazy("Perfil deportivo básico"),
     gettext_lazy("Tu deporte favorito, tu horario de entrenamiento y tu nivel de actividad.")),
    ("sports.preferences", gettext_lazy("Preferencias de entrenamiento"),
     gettext_lazy("Lo que confirmaste en Quantum Coach: actividad, metas y horarios.")),
    ("experiences.summary", gettext_lazy("Experiencias deportivas"),
     gettext_lazy("Qué agentes deportivos has completado, sin sus resultados.")),
    ("tailoring.measurements", gettext_lazy("Medidas para tallas"),
     gettext_lazy("Las medidas que escribas aquí, solo para sugerirte tallas.")),
    ("conversation.commerce_memory", gettext_lazy("Recordar mis elecciones"),
     gettext_lazy("La talla y el estilo que confirmes en el chat, durante 90 días.")),
)
ETIQUETAS_MEDIDAS = {
    "chest_cm": gettext_lazy("Pecho (cm)"),
    "waist_cm": gettext_lazy("Cintura (cm)"),
    "hip_cm": gettext_lazy("Cadera (cm)"),
    "inseam_cm": gettext_lazy("Tiro / entrepierna (cm)"),
}
# Nombre corto y como tomar cada medida, para la guia junto al formulario.
# Su orden numera las cintas del diagrama (1 pecho ... 4 entrepierna).
GUIA_MEDIDAS = {
    "chest_cm": (gettext_lazy("Pecho"),
                 gettext_lazy("Por la parte más llena del pecho, con la cinta horizontal bajo las axilas.")),
    "waist_cm": (gettext_lazy("Cintura"),
                 gettext_lazy("En la parte más estrecha del torso, por encima del ombligo.")),
    "hip_cm": (gettext_lazy("Cadera"),
               gettext_lazy("En la parte más ancha de los glúteos, con los pies juntos.")),
    "inseam_cm": (gettext_lazy("Entrepierna"),
                  gettext_lazy("Por dentro de la pierna, desde la entrepierna hasta el tobillo.")),
}
ETIQUETAS_MEMORIA = {
    "size": gettext_lazy("Talla"),
    "fit": gettext_lazy("Ajuste"),
    "color": gettext_lazy("Color"),
    "activity": gettext_lazy("Actividad"),
}
assert {s for s, _l, _d in SCOPES_VISIBLES} == set(SCOPE_FIELDS)
assert set(ETIQUETAS_MEMORIA) == set(MEMORY_KINDS)


def _volver():
    return redirect(reverse("edit_profile") + "#personalizacion")


def _vinculado(user):
    return ExternalIdentityLink.objects.filter(user=user).exists()


def contexto(user, now=None):
    """Datos para la seccion del perfil (inclusion tag)."""
    now = now or timezone.now()
    consent = CommercePersonalizationConsent.objects.filter(user=user).first()
    filas = []
    for scope, etiqueta, descripcion in SCOPES_VISIBLES:
        activo = consent is not None and consent.is_active(scope, now)
        vence = None
        if activo:
            vence = timezone.datetime.fromisoformat(consent.granted_at[scope]) + CONSENT_VALIDITY
        filas.append({"scope": scope, "etiqueta": etiqueta, "descripcion": descripcion,
                      "activo": activo, "vence": vence, "id": scope.replace(".", "-")})
    medidas_activo = consent is not None and consent.is_active("tailoring.measurements", now)
    medida = TailoringMeasurement.objects.filter(user=user).first() if medidas_activo else None
    memoria = []
    if consent is not None and consent.is_active("conversation.commerce_memory", now):
        memoria = [
            {"etiqueta": ETIQUETAS_MEMORIA.get(item.kind, item.kind), "valor": item.value, "hasta": item.expires_at}
            for item in CommerceMemoryItem.objects.filter(user=user, expires_at__gt=now).order_by("kind")
        ]
    activos = sum(1 for fila in filas if fila["activo"])
    return {
        "vinculado": _vinculado(user),
        # Sin OIDC habilitado en el servidor no hay con que vincular: no se
        # muestra un boton que no lleva a ninguna parte.
        "vincular_url": (
            reverse("gotogym_oidc:start") + "?" + urlencode({"next": reverse("edit_profile") + "#personalizacion"})
            if getattr(settings, "OIDC_HABILITADO", False) else ""
        ),
        "activos": activos,
        "total": len(filas),
        "todo_activo": activos == len(filas),
        "filas": filas,
        "medidas_activo": medidas_activo,
        "medidas": [
            {"campo": campo, "etiqueta": ETIQUETAS_MEDIDAS[campo], "minimo": minimo, "maximo": maximo,
             "valor": getattr(medida, campo) if medida else None,
             "nombre": GUIA_MEDIDAS[campo][0], "como": GUIA_MEDIDAS[campo][1]}
            for campo, (_nombre, minimo, maximo) in MEASUREMENT_FIELDS.items()
        ],
        "medidas_fecha": medida.captured_at if medida else None,
        "medidas_vigentes": medida.is_current(now) if medida else False,
        "memoria": memoria,
    }


@login_required
@require_POST
def guardar_permisos(request):
    elegidos = set(request.POST.getlist("scopes")) & set(SCOPE_FIELDS)
    vinculado = _vinculado(request.user)
    if elegidos and not vinculado:
        messages.error(request, _("Para personalizar con Quantum Coach primero vincula tu cuenta GoToGym."))
        return _volver()
    now = timezone.now()
    consent = CommercePersonalizationConsent.objects.filter(user=request.user).first()
    for scope in SCOPE_FIELDS:
        activo = consent is not None and consent.is_active(scope, now)
        quiere = scope in elegidos
        if quiere != activo:
            consentimiento.aplicar(request.user, scope, quiere, now)
    messages.success(request, _("Guardamos tus preferencias de personalización."))
    return _volver()


@login_required
@require_POST
def guardar_todo(request):
    """Interruptor "Personalizar con Quantum Coach": activa o apaga todos los
    permisos a la vez. Activar exige la cuenta vinculada; apagar, nunca."""
    activar = request.POST.get("accion") == "activar"
    if activar and not _vinculado(request.user):
        messages.error(request, _("Para personalizar con Quantum Coach primero vincula tu cuenta GoToGym."))
        return _volver()
    now = timezone.now()
    consent = CommercePersonalizationConsent.objects.filter(user=request.user).first()
    for scope in SCOPE_FIELDS:
        activo = consent is not None and consent.is_active(scope, now)
        if activo != activar:
            consentimiento.aplicar(request.user, scope, activar, now)
    if activar:
        messages.success(request, _("Activamos la personalización con Quantum Coach."))
    else:
        messages.success(request, _("Desactivamos la personalización con Quantum Coach."))
    return _volver()


@login_required
@require_POST
def guardar_medidas(request):
    consent = CommercePersonalizationConsent.objects.filter(user=request.user).first()
    if consent is None or not consent.is_active("tailoring.measurements") or not _vinculado(request.user):
        messages.error(request, _("Activa «Medidas para tallas» antes de guardar tus medidas."))
        return _volver()
    if request.POST.get("accion") == "borrar":
        TailoringMeasurement.objects.filter(user=request.user).delete()
        messages.success(request, _("Borramos tus medidas."))
        return _volver()

    valores = {}
    for campo, (_nombre, minimo, maximo) in MEASUREMENT_FIELDS.items():
        crudo = (request.POST.get(campo) or "").strip().replace(",", ".")
        if not crudo:
            valores[campo] = None
            continue
        try:
            numero = Decimal(crudo).quantize(Decimal("0.1"))
        except InvalidOperation:
            numero = None
        if numero is None or not minimo <= numero <= maximo:
            messages.error(request, _("Revisa %(campo)s: debe estar entre %(min)s y %(max)s cm.") % {
                "campo": ETIQUETAS_MEDIDAS[campo], "min": minimo, "max": maximo})
            return _volver()
        valores[campo] = numero
    if not any(v is not None for v in valores.values()):
        messages.error(request, _("Escribe al menos una medida."))
        return _volver()
    TailoringMeasurement.objects.update_or_create(
        user=request.user, defaults={**valores, "captured_at": timezone.now()},
    )
    messages.success(request, _("Guardamos tus medidas. Solo se usan para sugerirte tallas."))
    return _volver()


@never_cache
@csrf_protect
@login_required
@require_POST
def recordar(request):
    """Guarda la talla de una variante real cuando el cliente pulsa "Recordar".

    El navegador solo manda el id de la variante; la talla sale de la base.
    Exige enlace OIDC y el permiso `conversation.commerce_memory` vigente."""
    consent = CommercePersonalizationConsent.objects.filter(user=request.user).first()
    if consent is None or not consent.is_active("conversation.commerce_memory") or not _vinculado(request.user):
        return JsonResponse({"error": "consent_required"}, status=403)
    if len(request.body) > 256 or request.content_type != "application/json":
        return JsonResponse({"error": "invalid_request"}, status=400)
    try:
        datos = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_request"}, status=400)
    variante_id = datos.get("variant_id") if isinstance(datos, dict) else None
    if type(variante_id) is not int:
        return JsonResponse({"error": "invalid_request"}, status=400)
    variante = ProductVariant.objects.filter(pk=variante_id, is_active=True).first()
    talla = (variante.size or "").strip()[:40] if variante else ""
    if not talla or talla.upper() == "UNICA":
        return JsonResponse({"error": "no_size"}, status=400)
    now = timezone.now()
    CommerceMemoryItem.objects.update_or_create(
        user=request.user, kind="size",
        defaults={"value": talla, "confirmed_at": now, "expires_at": now + MEMORY_TTL},
    )
    return JsonResponse({"kind": "size", "value": talla})


@login_required
@require_POST
def olvidar_memoria(request):
    CommerceMemoryItem.objects.filter(user=request.user).delete()
    messages.success(request, _("Olvidamos tus elecciones guardadas."))
    return _volver()
