"""Atencion humana con radicado: solo hay radicado si la solicitud se guardo."""
import json
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings

from .models import SolicitudAtencion
from .services import crear_solicitud

URL = "/es/vendedor/atencion/"
VALIDA = {"nombre": "Ana Gil", "email": "ana@example.com", "motivo": "talla",
          "mensaje": "No sé si pedir M o L", "acepta_contacto": True}


@override_settings(ATENCION_EMAIL="equipo@example.com")
class CrearSolicitudTests(TestCase):
    def test_radicado_secuencial_y_correos_al_equipo_y_al_cliente(self):
        solicitud = crear_solicitud(**{**VALIDA, "origen": "quantum_coach"})
        self.assertRegex(solicitud.radicado, r"^GTG-\d{4}-\d{6}$")
        self.assertTrue(solicitud.radicado.endswith(f"{solicitud.pk:06d}"))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["ana@example.com", "equipo@example.com"])
        self.assertTrue(all(solicitud.radicado in m.subject for m in mail.outbox))
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.correo_cliente_enviado and solicitud.correo_equipo_enviado)

    def test_si_el_correo_falla_la_solicitud_existe_y_lo_registra(self):
        with mock.patch("atencion.services.correo.enviar_correo", side_effect=OSError("smtp")), \
                self.assertLogs("atencion.services", "ERROR"):
            solicitud = crear_solicitud(**{**VALIDA, "origen": "quantum_coach"})
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.radicado)
        self.assertFalse(solicitud.correo_cliente_enviado)

    def test_sin_autorizacion_de_contacto_no_se_crea(self):
        with self.assertRaises(ValueError):
            crear_solicitud(**{**VALIDA, "acepta_contacto": False, "origen": "quantum_coach"})
        self.assertFalse(SolicitudAtencion.objects.exists())


@override_settings(RATE_LIMIT_ENABLED=False)
class EndpointDelPanelTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def post(self, datos, client=None):
        return (client or self.client).post(URL, data=json.dumps(datos), content_type="application/json")

    def test_crea_y_devuelve_radicado_con_correo_enmascarado(self):
        respuesta = self.post(VALIDA)
        self.assertEqual(respuesta.status_code, 201)
        cuerpo = respuesta.json()
        self.assertRegex(cuerpo["radicado"], r"^GTG-\d{4}-\d{6}$")
        self.assertEqual(cuerpo["email"], "an***@example.com")
        self.assertTrue(cuerpo["correo_enviado"])
        solicitud = SolicitudAtencion.objects.get()
        self.assertEqual((solicitud.origen, solicitud.user), ("quantum_coach", None))

    def test_usuario_con_sesion_queda_asociado(self):
        user = get_user_model().objects.create_user(username="ana", email="ana@example.com", password="x-test")
        self.client.force_login(user)
        self.post(VALIDA)
        self.assertEqual(SolicitudAtencion.objects.get().user, user)

    def test_campos_invalidos_no_crean_nada(self):
        for cambio in ({"acepta_contacto": False}, {"acepta_contacto": "true"}, {"email": "no-es-correo"},
                       {"mensaje": "hey"}, {"motivo": "diagnostico"}, {"nombre": ""}):
            with self.subTest(cambio):
                self.assertEqual(self.post({**VALIDA, **cambio}).status_code, 400)
        self.assertFalse(SolicitudAtencion.objects.exists())

    def test_requiere_json_post_y_csrf(self):
        self.assertEqual(self.client.get(URL).status_code, 405)
        self.assertEqual(self.client.post(URL, data=VALIDA).status_code, 400)
        navegador = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(VALIDA, client=navegador).status_code, 403)
        self.assertFalse(SolicitudAtencion.objects.exists())

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_limite_de_frecuencia(self):
        from django.core.cache import cache
        cache.clear()
        codigos = [self.post(VALIDA).status_code for _ in range(6)]
        self.assertEqual(codigos[:5], [201] * 5)
        self.assertEqual(codigos[5], 429)


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100)
class PanelTests(TestCase):
    def test_el_formulario_existe_aunque_no_haya_ia(self):
        with override_settings(COACH_API_URL="", VENDEDOR_COACH_SIMULADO=False):
            html = self.client.get("/es/").content.decode()
        self.assertIn("data-vendedor-atencion", html)
        self.assertIn("data-vendedor-abrir-atencion", html)
        self.assertRegex(html, r'"atencionUrl": "/es/vendedor/atencion/"')

    def test_el_correo_del_usuario_se_precarga(self):
        user = get_user_model().objects.create_user(username="ana", email="ana@example.com", password="x-test",
                                                    first_name="Ana", last_name="Gil")
        self.client.force_login(user)
        html = self.client.get("/es/").content.decode()
        self.assertTrue(re.search(r'id="atencion-email"[^>]*value="ana@example.com"', html, re.S))


class BandejaAdminTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff", email="s@example.com", password="x-test", is_staff=True, is_superuser=True)
        self.cliente = get_user_model().objects.create_user(username="c", email="c@example.com", password="x-test")
        self.solicitud = crear_solicitud(**{**VALIDA, "origen": "quantum_coach"})

    def test_staff_ve_la_bandeja_el_detalle_y_cambia_el_estado(self):
        self.client.force_login(self.staff)
        lista = self.client.get("/es/admin-panel/atencion/").content.decode()
        self.assertIn(self.solicitud.radicado, lista)
        detalle = self.client.get(f"/es/admin-panel/atencion/{self.solicitud.pk}/").content.decode()
        self.assertIn("No sé si pedir M o L", detalle)
        self.client.post(f"/es/admin-panel/atencion/{self.solicitud.pk}/estado/", {"estado": "cerrada"})
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "cerrada")

    def test_un_cliente_no_entra_a_la_bandeja(self):
        self.client.force_login(self.cliente)
        self.assertNotEqual(self.client.get("/es/admin-panel/atencion/").status_code, 200)
        self.client.post(f"/es/admin-panel/atencion/{self.solicitud.pk}/estado/", {"estado": "cerrada"})
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "abierta")
