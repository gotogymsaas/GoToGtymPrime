"""Mi cuenta: permisos, medidas y memoria comercial; aviso discreto en el panel."""
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from gotogym_oidc.models import ExternalIdentityLink

from . import talla
from .models import (
    CommerceConsentAuditEvent,
    CommerceMemoryItem,
    CommercePersonalizationConsent,
    TailoringMeasurement,
)
from .test_utilidades import crear_producto

PERFIL = "/es/accounts/editar-perfil/"


class Base(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ana", email="ana@example.com", password="x-test", first_name="Ana", last_name="Gil",
        )
        self.client.force_login(self.user)

    def vincular(self):
        ExternalIdentityLink.objects.create(user=self.user, issuer="https://verified.example/v2.0", subject="oid-ana")

    def permisos(self, *scopes):
        return self.client.post(reverse("vendedor:personalizacion_permisos"), {"scopes": list(scopes)})

    def activos(self):
        row = CommercePersonalizationConsent.objects.filter(user=self.user).first()
        return row.active_scopes() if row else []


class SeccionDelPerfilTests(Base):
    @override_settings(OIDC_HABILITADO=True)
    def test_sin_vinculo_muestra_el_boton_para_vincular_en_vez_de_casillas(self):
        html = self.client.get(PERFIL).content.decode()
        seccion = html[html.index('id="personalizacion"'):]
        self.assertIn("Vincular con mi cuenta GoToGym", seccion)
        self.assertIn(reverse("gotogym_oidc:start") + "?next=", seccion)
        self.assertNotIn('id="scope-profile-basic"', seccion)
        self.assertNotIn('class="account-switch"', seccion)

    @override_settings(OIDC_HABILITADO=False)
    def test_sin_oidc_en_el_servidor_no_hay_boton_que_no_lleve_a_nada(self):
        self.assertNotIn("Vincular con mi cuenta GoToGym", self.client.get(PERFIL).content.decode())

    def test_con_vinculo_y_sin_decision_el_interruptor_esta_apagado(self):
        self.vincular()
        html = self.client.get(PERFIL).content.decode()
        seccion = html[html.index('id="personalizacion"'):]
        self.assertIn('role="switch" aria-checked="false"', seccion)
        self.assertIn("Elegir uno por uno", seccion)
        self.assertNotIn("checked>", seccion.replace('aria-checked="false"', ""))
        self.assertNotIn("Mis medidas para tallas", html)

    def test_anonimo_no_ve_la_seccion(self):
        self.client.logout()
        self.assertNotEqual(self.client.get(PERFIL).status_code, 200)


class PermisosTests(Base):
    def test_conceder_y_revocar_desde_el_formulario_queda_auditado(self):
        self.vincular()
        respuesta = self.permisos("profile.basic", "sports.preferences")
        self.assertRedirects(respuesta, reverse("edit_profile") + "#personalizacion", fetch_redirect_response=False)
        self.assertEqual(self.activos(), ["profile.basic", "sports.preferences"])
        self.permisos("sports.preferences")
        self.assertEqual(self.activos(), ["sports.preferences"])
        self.assertEqual(
            list(CommerceConsentAuditEvent.objects.order_by("pk").values_list("scope", "allowed")),
            [("profile.basic", True), ("sports.preferences", True), ("profile.basic", False)],
        )

    def test_sin_vinculo_no_concede(self):
        self.permisos("profile.basic")
        self.assertEqual(self.activos(), [])

    def test_sin_vinculo_si_puede_revocar(self):
        link = ExternalIdentityLink.objects.create(user=self.user, issuer="https://v/v2.0", subject="oid")
        self.permisos("profile.basic")
        link.delete()
        self.permisos()
        self.assertEqual(self.activos(), [])

    def test_scope_inventado_se_ignora(self):
        self.vincular()
        self.permisos("clinical.history")
        self.assertEqual(self.activos(), [])

    def test_revocar_medidas_borra_las_medidas_y_revocar_memoria_borra_la_memoria(self):
        self.vincular()
        self.permisos("tailoring.measurements", "conversation.commerce_memory")
        now = timezone.now()
        TailoringMeasurement.objects.create(user=self.user, waist_cm=Decimal("72.0"), captured_at=now)
        CommerceMemoryItem.objects.create(user=self.user, kind="size", value="M", confirmed_at=now,
                                          expires_at=now + timedelta(days=90))
        self.permisos()
        self.assertFalse(TailoringMeasurement.objects.exists())
        self.assertFalse(CommerceMemoryItem.objects.exists())

    def test_requiere_post_y_sesion(self):
        self.assertEqual(self.client.get(reverse("vendedor:personalizacion_permisos")).status_code, 405)
        self.client.logout()
        self.assertEqual(self.permisos("profile.basic").status_code, 302)


class MedidasTests(Base):
    def setUp(self):
        super().setUp()
        self.vincular()

    def guardar(self, **datos):
        return self.client.post(reverse("vendedor:personalizacion_medidas"), datos)

    def test_sin_permiso_no_guarda(self):
        self.guardar(waist_cm="72")
        self.assertFalse(TailoringMeasurement.objects.exists())

    def test_guarda_con_permiso_acepta_coma_decimal_y_se_ve_en_el_perfil(self):
        self.permisos("tailoring.measurements")
        self.guardar(chest_cm="92,5", waist_cm="72", hip_cm="", inseam_cm="")
        medida = TailoringMeasurement.objects.get()
        self.assertEqual((medida.chest_cm, medida.waist_cm, medida.hip_cm), (Decimal("92.5"), Decimal("72.0"), None))
        html = self.client.get(PERFIL).content.decode()
        self.assertIn("Mis medidas para tallas", html)
        self.assertIn('value="92.5"', html)

    def test_el_diagrama_marca_donde_va_cada_medida_y_numera_igual_que_el_formulario(self):
        self.permisos("tailoring.measurements")
        html = self.client.get(PERFIL).content.decode()
        guia = html[html.index('class="medida-guia"'):html.index("</figure>")]
        self.assertIn('role="img"', guia)
        self.assertIn("Dónde se toma cada medida en el cuerpo", guia)
        for campo in ("chest_cm", "waist_cm", "hip_cm", "inseam_cm"):
            self.assertEqual(guia.count(f'data-medida="{campo}"'), 2, campo)  # cinta en el dibujo y su indicacion
        self.assertIn("desde la entrepierna hasta el tobillo", guia)
        formulario = html[html.index("</figure>"):]
        orden = [formulario.index(f'for="medida-{c}"') for c in ("chest_cm", "waist_cm", "hip_cm", "inseam_cm")]
        self.assertEqual(orden, sorted(orden), "los numeros 1-4 del dibujo siguen este orden")

    def test_fuera_de_rango_o_vacio_se_rechaza(self):
        self.permisos("tailoring.measurements")
        self.guardar(waist_cm="7")
        self.guardar(waist_cm="abc")
        self.guardar()
        self.assertFalse(TailoringMeasurement.objects.exists())

    def test_borrar(self):
        self.permisos("tailoring.measurements")
        self.guardar(waist_cm="72")
        self.guardar(accion="borrar")
        self.assertFalse(TailoringMeasurement.objects.exists())

    def test_medidas_de_otro_usuario_no_se_ven(self):
        otro = get_user_model().objects.create_user(username="beto", email="b@example.com", password="x-test")
        TailoringMeasurement.objects.create(user=otro, waist_cm=Decimal("99.5"), captured_at=timezone.now())
        self.permisos("tailoring.measurements")
        self.assertNotIn("99.5", self.client.get(PERFIL).content.decode())


class OrientacionDeTallaTests(Base):
    def medir(self, dias=0, **valores):
        return TailoringMeasurement.objects.create(
            user=self.user, captured_at=timezone.now() - timedelta(days=dias),
            **{k: Decimal(v) for k, v in valores.items()})

    def test_dimensiones_coincidentes_dan_una_sugerencia(self):
        self.medir(chest_cm="90", waist_cm="72", hip_cm="96")
        guia = talla.orientacion(self.user)
        self.assertEqual(guia["by_dimension"], {"busto": "M", "cintura": "M", "cadera": "M"})
        self.assertEqual(guia["suggestion"], "M")
        self.assertEqual(guia["source"], "general_size_guide")
        self.assertNotIn("72", json.dumps(guia), "nunca viajan los centimetros")

    def test_dimensiones_distintas_no_eligen_por_la_persona(self):
        self.medir(waist_cm="72", hip_cm="103")
        guia = talla.orientacion(self.user)
        self.assertEqual(guia["by_dimension"], {"cintura": "M", "cadera": "L"})
        self.assertIsNone(guia["suggestion"])

    def test_entre_dos_rangos_elige_la_mayor_y_fuera_de_guia_se_informa(self):
        self.medir(waist_cm="69.5", hip_cm="150")
        guia = talla.orientacion(self.user)
        self.assertEqual(guia["by_dimension"], {"cintura": "M", "cadera": "out_of_guide"})
        self.assertIsNone(guia["suggestion"])

    def test_medidas_viejas_o_ausentes_no_orientan(self):
        self.assertIsNone(talla.orientacion(self.user))
        self.medir(dias=200, waist_cm="72")
        self.assertIsNone(talla.orientacion(self.user))


class RecordarTests(Base):
    URL = "/es/vendedor/personalizacion/recordar/"

    def setUp(self):
        super().setUp()
        _, (self.m, self.unica) = crear_producto("Legging", [("M", "Negro", 3), ("UNICA", "Gris", 2)])

    def recordar(self, variant_id):
        return self.client.post(self.URL, data=json.dumps({"variant_id": variant_id}), content_type="application/json")

    def test_sin_permiso_no_recuerda(self):
        self.vincular()
        self.assertEqual(self.recordar(self.m.pk).status_code, 403)
        self.assertFalse(CommerceMemoryItem.objects.exists())

    def test_con_permiso_guarda_la_talla_real_de_la_variante_por_90_dias(self):
        self.vincular()
        self.permisos("conversation.commerce_memory")
        respuesta = self.recordar(self.m.pk)
        self.assertEqual(respuesta.json(), {"kind": "size", "value": "M"})
        item = CommerceMemoryItem.objects.get()
        self.assertAlmostEqual((item.expires_at - item.confirmed_at).days, 90)
        self.assertIn("Talla: M", self.client.get(PERFIL).content.decode())

    def test_talla_unica_o_variante_inexistente_no_se_recuerdan(self):
        self.vincular()
        self.permisos("conversation.commerce_memory")
        self.assertEqual(self.recordar(self.unica.pk).status_code, 400)
        self.assertEqual(self.recordar(999999).status_code, 400)
        self.assertEqual(self.recordar("M").status_code, 400)
        self.assertFalse(CommerceMemoryItem.objects.exists())

    def test_olvidar_borra_todo(self):
        self.vincular()
        self.permisos("conversation.commerce_memory")
        self.recordar(self.m.pk)
        self.client.post(reverse("vendedor:personalizacion_olvidar"))
        self.assertFalse(CommerceMemoryItem.objects.exists())


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100, VENDEDOR_COACH_SIMULADO=True)
class InvitacionEnElPanelTests(Base):
    def html(self):
        return self.client.get("/es/").content.decode()

    def test_vinculado_sin_permisos_ve_la_invitacion(self):
        self.vincular()
        self.assertIn("data-vendedor-invitacion", self.html())

    def test_con_algun_permiso_ya_no_se_invita(self):
        self.vincular()
        self.permisos("profile.basic")
        self.assertNotIn("data-vendedor-invitacion", self.html())

    def test_el_boton_recordar_solo_se_habilita_con_permiso(self):
        self.vincular()
        self.assertIn('"puedeRecordar": false', self.html())
        self.permisos("conversation.commerce_memory")
        self.assertIn('"puedeRecordar": true', self.html())

    def test_sin_vinculo_o_anonimo_no_se_invita(self):
        self.assertNotIn("data-vendedor-invitacion", self.html())
        self.client.logout()
        self.assertNotIn("data-vendedor-invitacion", self.html())
