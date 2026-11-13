"""Personalización activa al crear el perfil e interruptor único en Mi cuenta."""
from datetime import timedelta
from decimal import Decimal

from accounts.signals import perfil_creado
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from gotogym_oidc.models import ExternalIdentityLink

from .consentimiento import aplicar, conceder_al_crear_perfil
from .models import (
    SCOPE_FIELDS,
    CommerceConsentAuditEvent,
    CommerceMemoryItem,
    CommercePersonalizationConsent,
    TailoringMeasurement,
)

PERFIL = "/es/accounts/editar-perfil/"
TODOS = sorted(SCOPE_FIELDS)


def _activos(user):
    row = CommercePersonalizationConsent.objects.filter(user=user).first()
    return row.active_scopes() if row else []


class AlCrearElPerfilTests(TestCase):
    def test_el_registro_activa_todos_los_permisos_y_queda_auditado(self):
        respuesta = self.client.post(reverse("register"), {
            "first_name": "Luis", "email": "luis@example.com", "password1": "Clave-segura1!", "accepted_terms": "on",
        })
        self.assertEqual(respuesta.status_code, 302)
        usuario = get_user_model().objects.get(email="luis@example.com")
        self.assertEqual(_activos(usuario), TODOS)
        self.assertEqual(CommerceConsentAuditEvent.objects.filter(user=usuario, allowed=True).count(), len(TODOS))

    def test_el_formulario_de_registro_lo_avisa_junto_a_los_terminos(self):
        html = self.client.get(reverse("register")).content.decode()
        self.assertIn('aria-describedby="personalizacion-aviso"', html)
        self.assertIn("Al crear tu cuenta se activa la personalización con Quantum Coach", html)
        self.assertIn(reverse("politica_tratamiento_datos"), html)

    def test_un_registro_fallido_no_concede_nada(self):
        self.client.post(reverse("register"), {"first_name": "Luis", "email": "luis@example.com", "password1": "x"})
        self.assertFalse(CommercePersonalizationConsent.objects.exists())

    def test_aceptar_los_terminos_tras_el_primer_acceso_con_gotogym_tambien_activa(self):
        usuario = get_user_model().objects.create_user(email="sso@example.com", username="sso", password="x")
        self.client.force_login(usuario)
        self.client.post(reverse("accept_terms"), {"accepted_terms": "on", "next": "/es/"})
        self.assertEqual(_activos(usuario), TODOS)

    def test_no_reactiva_lo_que_la_persona_ya_apago(self):
        usuario = get_user_model().objects.create_user(email="ana@example.com", username="ana", password="x")
        aplicar(usuario, "profile.basic", True)
        aplicar(usuario, "profile.basic", False)
        perfil_creado.send(sender=type(usuario), user=usuario)
        self.assertEqual(_activos(usuario), [])
        self.assertIsNone(conceder_al_crear_perfil(usuario))

    def test_las_cuentas_existentes_no_se_activan_solas(self):
        usuario = get_user_model().objects.create_user(email="vieja@example.com", username="vieja", password="x")
        self.assertEqual(_activos(usuario), [])


class InterruptorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="eva@example.com", username="eva", password="x")
        self.client.force_login(self.user)

    def vincular(self):
        ExternalIdentityLink.objects.create(user=self.user, issuer="https://verified.example/v2.0", subject="oid-eva")

    def todo(self, accion):
        return self.client.post(reverse("vendedor:personalizacion_todo"), {"accion": accion})

    def test_activar_y_desactivar_todo_de_una_vez(self):
        self.vincular()
        self.assertRedirects(self.todo("activar"), reverse("edit_profile") + "#personalizacion",
                             fetch_redirect_response=False)
        self.assertEqual(_activos(self.user), TODOS)
        self.assertIn('role="switch" aria-checked="true"', self.client.get(PERFIL).content.decode())
        self.todo("desactivar")
        self.assertEqual(_activos(self.user), [])

    def test_desactivar_borra_medidas_y_memoria(self):
        self.vincular()
        self.todo("activar")
        now = timezone.now()
        TailoringMeasurement.objects.create(user=self.user, waist_cm=Decimal("72.0"), captured_at=now)
        CommerceMemoryItem.objects.create(user=self.user, kind="size", value="M", confirmed_at=now,
                                          expires_at=now + timedelta(days=90))
        self.todo("desactivar")
        self.assertFalse(TailoringMeasurement.objects.exists())
        self.assertFalse(CommerceMemoryItem.objects.exists())

    def test_sin_vinculo_no_se_activa_a_mano_pero_si_se_puede_apagar(self):
        self.todo("activar")
        self.assertEqual(_activos(self.user), [])
        conceder_al_crear_perfil(self.user)  # como si viniera del registro
        html = self.client.get(PERFIL).content.decode()
        self.assertIn("empezará a funcionar cuando vincules tu cuenta GoToGym", html)
        self.assertIn("Desactivar personalización", html)
        self.todo("desactivar")
        self.assertEqual(_activos(self.user), [])

    def test_activado_en_parte_lo_dice_y_abre_el_detalle(self):
        self.vincular()
        aplicar(self.user, "profile.basic", True)
        seccion = self.client.get(PERFIL).content.decode()
        self.assertIn("Activada en 1 de 5 permisos", seccion)
        self.assertIn('role="switch" aria-checked="false"', seccion)
        self.assertIn('account-personalizacion-detalle" open', seccion)
        # Pulsar el interruptor en ese estado activa todo.
        self.todo("activar")
        self.assertEqual(_activos(self.user), TODOS)

    def test_requiere_post_y_sesion(self):
        self.assertEqual(self.client.get(reverse("vendedor:personalizacion_todo")).status_code, 405)
        self.client.logout()
        self.assertEqual(self.todo("desactivar").status_code, 302)
