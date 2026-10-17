"""Ramas de las vistas del afiliado: re-postulacion, accesos sin perfil,
solicitud de comision y baja del programa."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from .models import EstadoAfiliado, PerfilAfiliado, WithdrawalRequest, WithdrawalStatus
from .services import aplicar_bajas_vencidas, approve_afiliado
from .tests import AfiliadoTestBase, datos_postulacion


def _mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class RePostulacionTests(AfiliadoTestBase):
    def _postular(self, codigo='NUEVOCODIGO'):
        self.client.force_login(self.afiliado_user)
        return self.client.post(reverse('afiliado_suscribete'), datos_postulacion(codigo))

    def test_quien_se_dio_de_baja_puede_volver_a_postularse_con_otro_codigo(self):
        perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('afiliado_quitar_suscripcion'))
        # La baja exige un preaviso: se hace efectiva al vencer.
        aplicar_bajas_vencidas(ahora=timezone.now() + timedelta(days=16))

        respuesta = self._postular('REGRESO2026')

        self.assertRedirects(respuesta, reverse('afiliado_dashboard'), fetch_redirect_response=False)
        perfil.refresh_from_db()
        self.assertTrue(perfil.is_active)
        self.assertEqual(perfil.status, EstadoAfiliado.PENDING)
        self.assertEqual(perfil.referral_code, 'REGRESO2026')
        self.assertIsNone(perfil.reviewed_at)
        self.assertIn('enviada de nuevo', _mensajes(respuesta)[-1])

    def test_un_rechazado_puede_postularse_otra_vez(self):
        perfil = PerfilAfiliado.objects.create(user=self.afiliado_user, status=EstadoAfiliado.REJECTED)

        respuesta = self._postular('SEGUNDAVEZ')

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, EstadoAfiliado.PENDING)
        self.assertEqual(perfil.referral_code, 'SEGUNDAVEZ')
        self.assertIn('enviada de nuevo', _mensajes(respuesta)[-1])

    def test_enviar_la_solicitud_dos_veces_no_la_duplica(self):
        PerfilAfiliado.objects.create(user=self.afiliado_user, status=EstadoAfiliado.PENDING)

        respuesta = self._postular()

        self.assertEqual(PerfilAfiliado.objects.filter(user=self.afiliado_user).count(), 1)
        self.assertIn('en revisión', _mensajes(respuesta)[-1])

    def test_un_aprobado_que_reenvia_el_formulario_solo_recibe_un_aviso(self):
        perfil = self._crear_perfil_aprobado()
        codigo = perfil.referral_code

        respuesta = self._postular('OTROCODIGO')

        perfil.refresh_from_db()
        self.assertEqual(perfil.referral_code, codigo)
        self.assertIn('Ya eres afiliado', _mensajes(respuesta)[-1])

    def test_el_propio_codigo_no_cuenta_como_ocupado_al_re_postularse(self):
        perfil = PerfilAfiliado.objects.create(
            user=self.afiliado_user, status=EstadoAfiliado.REJECTED, referral_code='MISMOCODIGO',
        )

        self._postular('MISMOCODIGO')

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, EstadoAfiliado.PENDING)

    def test_un_codigo_que_ya_es_cupon_de_otro_se_rechaza(self):
        otro = PerfilAfiliado.objects.create(
            user=self.comprador, status=EstadoAfiliado.PENDING, referral_code='CUPONAJENO',
        )
        approve_afiliado(otro, self.admin)

        respuesta = self._postular('CUPONAJENO')

        self.assertFalse(PerfilAfiliado.objects.filter(user=self.afiliado_user).exists())
        self.assertIn('ya está en uso', ' '.join(respuesta.context['form'].errors['referral_code']))

    def test_un_error_de_base_de_datos_al_guardar_se_informa_y_no_deja_un_perfil_a_medias(self):
        with patch('afiliados.views.SocialNetwork.objects.bulk_create', side_effect=IntegrityError):
            respuesta = self._postular()

        self.assertRedirects(respuesta, reverse('afiliado_suscribete'), fetch_redirect_response=False)
        self.assertIn('Hubo un problema', _mensajes(respuesta)[-1])
        self.assertFalse(PerfilAfiliado.objects.filter(user=self.afiliado_user).exists())


class AccesoSinPerfilTests(AfiliadoTestBase):
    def setUp(self):
        self.client.force_login(self.afiliado_user)

    def test_el_panel_sin_perfil_lleva_al_formulario(self):
        self.assertRedirects(self.client.get(reverse('afiliado_dashboard')), reverse('afiliado_suscribete'))

    def test_compras_referidas_exige_ser_afiliado_aprobado(self):
        PerfilAfiliado.objects.create(user=self.afiliado_user, status=EstadoAfiliado.PENDING)
        self.assertRedirects(
            self.client.get(reverse('afiliado_compras_referidas')), reverse('afiliado_dashboard'),
            fetch_redirect_response=False,
        )

    def test_solicitar_comision_exige_ser_afiliado_aprobado(self):
        respuesta = self.client.post(reverse('afiliado_solicitar_retiro'), {'payment_details': 'x'})
        self.assertRedirects(respuesta, reverse('afiliado_dashboard'), fetch_redirect_response=False)
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_quitar_suscripcion_sin_perfil_solo_vuelve_a_la_portada(self):
        respuesta = self.client.post(reverse('afiliado_quitar_suscripcion'))
        self.assertRedirects(respuesta, '/', fetch_redirect_response=False)


class SolicitarComisionTests(AfiliadoTestBase):
    def setUp(self):
        self.perfil = self._crear_perfil_aprobado()
        self._inscribir_cuenta(self.perfil)
        self.client.force_login(self.afiliado_user)
        self.url = reverse('afiliado_solicitar_retiro')

    def test_un_get_no_hace_nada(self):
        self.assertRedirects(self.client.get(self.url), reverse('afiliado_dashboard'), fetch_redirect_response=False)

    def test_sin_cuenta_bre_b_se_pide_inscribirla(self):
        self.perfil.payout_account.delete()
        self._pedido_entregado(self.perfil)
        respuesta = self.client.post(self.url, {'payment_details': 'Cuenta 123'})
        self.assertIn('Inscribe tu cuenta Bre-B', _mensajes(respuesta)[-1])
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_un_mensaje_demasiado_largo_se_rechaza(self):
        respuesta = self.client.post(self.url, {'payment_details': 'x' * 1001})
        self.assertIn('muy largo', _mensajes(respuesta)[-1])
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_sin_comisiones_disponibles_se_avisa(self):
        respuesta = self.client.post(self.url, {'payment_details': 'Cuenta 123'})
        self.assertIn('No tienes comisiones confirmadas disponibles', _mensajes(respuesta)[-1])

    def test_con_saldo_se_crea_la_solicitud_y_una_segunda_se_bloquea(self):
        self._pedido_entregado(self.perfil)

        primera = self.client.post(self.url, {'payment_details': 'Cuenta 123'})
        self.assertIn('enviada', _mensajes(primera)[-1])
        self.assertEqual(WithdrawalRequest.objects.filter(status=WithdrawalStatus.PENDING).count(), 1)

        segunda = self.client.post(self.url, {'payment_details': 'Cuenta 123'})
        self.assertIn('ya tienes una solicitud', _mensajes(segunda)[-1].lower())
        self.assertEqual(WithdrawalRequest.objects.count(), 1)


class PanelConEstadisticasTests(AfiliadoTestBase):
    def test_el_panel_calcula_la_conversion_cuando_hay_clics(self):
        perfil = self._crear_perfil_aprobado()
        perfil.referral_clicks.create()
        perfil.referral_clicks.create()
        perfil.total_referred = 1
        perfil.save(update_fields=['total_referred'])
        self.client.force_login(self.afiliado_user)

        respuesta = self.client.get(reverse('afiliado_dashboard'))

        self.assertEqual(respuesta.context['click_count'], 2)
        self.assertEqual(respuesta.context['conversion_rate'], '50.0')
