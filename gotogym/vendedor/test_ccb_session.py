"""Cognitive Commerce Bridge: aislamiento de sesión y consentimiento explícito."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings
from gotogym_oidc.models import ExternalIdentityLink

from . import conversacion, estado
from .consentimiento import aplicar
from .models import CommercePersonalizationConsent

ISSUER = "https://verified.example/tenant/v2.0"
CONFIG = {
    "GOTOGYM_OIDC": {"ISSUER": ISSUER, "SUBJECT_CLAIM": "oid"},
    "VENDEDOR_CONTRATO_V2": True,
    "VENDEDOR_IDENTIDAD_CLAVE_ID": "prime-id-1",
    "VENDEDOR_IDENTIDAD_SECRETO": "safe-test-secret-distinct",
}


@override_settings(**CONFIG)
class CommerceIdentityEpochTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ana", email="ana@example.com", password="x"
        )
        self.other = get_user_model().objects.create_user(
            username="beto", email="beto@example.com", password="x"
        )
        self.rf = RequestFactory()

    def request(self, user):
        request = self.rf.get("/es/vendedor/estado/")
        request.user = user
        request.session = SessionStore()
        return request

    def test_anonymous_and_local_account_use_distinct_epochs(self):
        guest = estado.estado_usuario(self.request(AnonymousUser()))
        local = estado.estado_usuario(self.request(self.user))
        self.assertEqual(guest["mode"], "anonymous")
        self.assertEqual(local["mode"], "link_required")
        self.assertNotEqual(guest["epoch"], local["epoch"])
        self.assertNotIn(str(self.user.email), str(local))

    def test_link_and_consent_transition_to_linked_without_leaking_oid(self):
        request = self.request(self.user)
        start = estado.estado_usuario(request)
        ExternalIdentityLink.objects.create(user=self.user, issuer=ISSUER, subject="oid-ana")
        needs_consent = estado.estado_usuario(request)
        self.assertEqual(needs_consent["mode"], "consent_required")
        self.assertNotEqual(needs_consent["epoch"], start["epoch"])
        aplicar(self.user, "profile.display_name", True)
        linked = estado.estado_usuario(request)
        self.assertEqual(linked["mode"], "linked")
        self.assertTrue(linked["personalization_ready"])
        self.assertEqual(linked["scope_count"], 1)
        self.assertNotEqual(linked["epoch"], needs_consent["epoch"])
        self.assertNotIn("oid-ana", str(linked))
        aplicar(self.user, "profile.display_name", False)
        revoked = estado.estado_usuario(request)
        self.assertEqual(revoked["mode"], "consent_required")
        self.assertNotEqual(revoked["epoch"], linked["epoch"])

    def test_other_user_never_reuses_epoch(self):
        self.assertNotEqual(
            estado.estado_usuario(self.request(self.user))["epoch"],
            estado.estado_usuario(self.request(self.other))["epoch"],
        )

    def test_register_signal_does_not_grant_identity_scope(self):
        from accounts.signals import perfil_creado

        perfil_creado.send(sender=type(self.user), user=self.user)
        self.assertFalse(CommercePersonalizationConsent.objects.filter(user=self.user).exists())

    def test_server_conversation_rotates_when_epoch_changes(self):
        session = {}
        first = conversacion.obtener(session, ahora=1000, binding="guest-epoch")
        old = first["id"]
        same = conversacion.obtener(session, ahora=1002, binding="guest-epoch")
        self.assertEqual(same["id"], old)
        after = conversacion.obtener(session, ahora=1003, binding="linked-epoch")
        self.assertNotEqual(after["id"], old)
        self.assertEqual(after["turnos"], 0)
