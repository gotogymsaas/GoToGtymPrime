"""Identity Bridge: la asercion solo existe con enlace OIDC y consentimiento vigente."""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from gotogym_oidc.models import ExternalIdentityLink

from . import contrato, identidad, paquete
from .models import SCOPE_FIELDS, CommercePersonalizationConsent

ISSUER = "https://verified.example/tenant/v2.0"
SECRETO = "identidad-solo-pruebas"
CONF = {"ISSUER": ISSUER, "SUBJECT_CLAIM": "oid"}
CREDENCIAL = {
    "VENDEDOR_IDENTIDAD_CLAVE_ID": "prime-id-1",
    "VENDEDOR_IDENTIDAD_SECRETO": SECRETO,
    "GOTOGYM_OIDC": CONF,
}


def conceder(user, *scopes):
    ahora = timezone.now().isoformat()
    return CommercePersonalizationConsent.objects.create(
        user=user, version=2, granted_at={s: ahora for s in scopes},
        **{SCOPE_FIELDS[s]: True for s in scopes},
    )


@override_settings(**CREDENCIAL)
class IdentityAssertionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.ana = User.objects.create_user(username="ana", email="ana@example.com", password="x-test")
        self.beto = User.objects.create_user(username="beto", email="beto@example.com", password="x-test")

    def vincular(self, user, oid):
        ExternalIdentityLink.objects.create(user=user, issuer=ISSUER, subject=oid)

    def test_sin_enlace_no_hay_asercion(self):
        conceder(self.ana, "profile.basic")
        self.assertIsNone(identidad.emitir(self.ana))

    def test_enlace_sin_consentimiento_no_hay_asercion(self):
        self.vincular(self.ana, "oid-ana")
        self.assertIsNone(identidad.emitir(self.ana))

    def test_anonimo_no_hay_asercion(self):
        self.assertIsNone(identidad.emitir(AnonymousUser()))

    @override_settings(VENDEDOR_IDENTIDAD_SECRETO="")
    def test_sin_credencial_no_hay_asercion(self):
        self.vincular(self.ana, "oid-ana")
        conceder(self.ana, "profile.basic")
        self.assertIsNone(identidad.emitir(self.ana))

    def test_enlace_de_otro_issuer_no_cuenta(self):
        ExternalIdentityLink.objects.create(user=self.ana, issuer="https://otro/v2.0", subject="oid-ana")
        conceder(self.ana, "profile.basic")
        self.assertIsNone(identidad.emitir(self.ana))

    def test_asercion_valida_lleva_solo_scopes_vigentes(self):
        self.vincular(self.ana, "oid-ana")
        conceder(self.ana, "sports.preferences", "tailoring.measurements")
        carga = identidad.verificar(SECRETO, identidad.emitir(self.ana, ahora=1000), ahora=1010)
        self.assertEqual(carga["idp_issuer"], ISSUER)
        self.assertEqual(carga["idp_subject"], "oid-ana")
        self.assertEqual(carga["scopes"], ["sports.preferences", "tailoring.measurements"])
        self.assertEqual(carga["aud"], identidad.AUDIENCIA)
        self.assertEqual(carga["exp"] - carga["iat"], 60)

    def test_dos_usuarios_reciben_identidades_distintas(self):
        self.vincular(self.ana, "oid-ana")
        self.vincular(self.beto, "oid-beto")
        conceder(self.ana, "profile.basic")
        conceder(self.beto, "profile.basic")
        a = identidad.verificar(SECRETO, identidad.emitir(self.ana, ahora=1000), ahora=1000)
        b = identidad.verificar(SECRETO, identidad.emitir(self.beto, ahora=1000), ahora=1000)
        self.assertEqual((a["idp_subject"], b["idp_subject"]), ("oid-ana", "oid-beto"))
        self.assertNotEqual(a["jti"], b["jti"])

    def test_rechaza_firma_ajena_caducada_y_repetida(self):
        self.vincular(self.ana, "oid-ana")
        conceder(self.ana, "profile.basic")
        bloque = identidad.emitir(self.ana, ahora=1000)
        with self.assertRaisesMessage(ValueError, "mismatch"):
            identidad.verificar("otro-secreto", bloque, ahora=1000)
        with self.assertRaisesMessage(ValueError, "expired"):
            identidad.verificar(SECRETO, bloque, ahora=1060)
        usados = set()
        identidad.verificar(SECRETO, bloque, ahora=1001, usados=usados)
        with self.assertRaisesMessage(ValueError, "replay"):
            identidad.verificar(SECRETO, bloque, ahora=1002, usados=usados)

    def test_carga_alterada_invalida_la_firma(self):
        self.vincular(self.ana, "oid-ana")
        conceder(self.ana, "profile.basic")
        bloque = dict(identidad.emitir(self.ana, ahora=1000))
        bloque["assertion"] = bloque["assertion"][:-2] + "AA"
        with self.assertRaisesMessage(ValueError, "mismatch"):
            identidad.verificar(SECRETO, bloque, ahora=1000)


@override_settings(**CREDENCIAL)
class PaqueteV2Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ana", email="ana@example.com", password="x-test",
        )
        ExternalIdentityLink.objects.create(user=self.user, issuer=ISSUER, subject="oid-ana")
        conceder(self.user, "profile.basic")

    def solicitud(self, user):
        request = RequestFactory().post("/es/vendedor/mensaje/")
        request.user = user
        request.session = {}
        return paquete.armar_solicitud(request, "Busco unos leggins", "shop-12345678")

    @override_settings(VENDEDOR_CONTRATO_V2=False)
    def test_con_v2_apagado_el_paquete_es_v1(self):
        self.assertNotIn("identity", self.solicitud(self.user))

    @override_settings(VENDEDOR_CONTRATO_V2=True)
    def test_con_v2_encendido_viaja_la_asercion_validada(self):
        solicitud = self.solicitud(self.user)
        self.assertIn("identity", solicitud)
        contrato.validar_solicitud(solicitud)
        carga = identidad.verificar(SECRETO, solicitud["identity"])
        # El correo nunca viaja, ni en el paquete ni dentro de la asercion.
        self.assertNotIn("ana@example.com", json.dumps(solicitud))
        self.assertNotIn("ana@example.com", json.dumps(carga))

    @override_settings(VENDEDOR_CONTRATO_V2=True)
    def test_visitante_anonimo_sigue_en_v1(self):
        self.assertNotIn("identity", self.solicitud(AnonymousUser()))

    def test_contrato_rechaza_identidad_en_visitante_anonimo(self):
        solicitud = self.solicitud(AnonymousUser())
        solicitud["identity"] = {"key_id": "k", "assertion": "x", "signature": "0" * 64}
        with self.assertRaises(contrato.ContratoInvalido):
            contrato.validar_solicitud(solicitud)
