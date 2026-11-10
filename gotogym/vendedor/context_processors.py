from django.utils.functional import SimpleLazyObject

from .exposicion import coach_configurado, visible_para


def _invitar_a_personalizar(request):
    """True si la cuenta esta vinculada y no tiene ningun permiso vigente: el
    panel le recuerda, con discrecion, que puede activarlo en Mi cuenta."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    from gotogym_oidc.models import ExternalIdentityLink

    from .models import CommercePersonalizationConsent

    if not ExternalIdentityLink.objects.filter(user=user).exists():
        return False
    consent = CommercePersonalizationConsent.objects.filter(user=user).first()
    return consent is None or not consent.active_scopes()


def _puede_recordar(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    from .models import CommercePersonalizationConsent

    consent = CommercePersonalizationConsent.objects.filter(user=user).first()
    return consent is not None and consent.is_active('conversation.commerce_memory')


def vendedor(request):
    """Expone a las plantillas si se muestra el boton de Quantum Coach y si
    hay una IA que responda. Con el interruptor apagado o fuera del grupo
    expuesto, el sitio es identico al de antes: ni boton ni panel. Sin IA
    configurada se muestra igual y el panel avisa que no esta disponible."""
    visible = visible_para(request)
    disponible = visible and coach_configurado()
    return {
        'vendedor_visible': visible,
        'vendedor_disponible': disponible,
        # Perezoso: solo consulta la base si el panel llega a pintarse.
        'vendedor_invitar_personalizar': SimpleLazyObject(
            lambda: disponible and _invitar_a_personalizar(request)),
        'vendedor_puede_recordar': SimpleLazyObject(lambda: disponible and _puede_recordar(request)),
    }
