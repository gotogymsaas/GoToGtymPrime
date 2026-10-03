"""Ramas de las vistas del afiliado: re-postulacion, accesos sin perfil,
solicitud de comision y baja del programa."""
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.db import IntegrityError
from django.urls import reverse

from .models import InfluencerProfile, InfluencerStatus, WithdrawalRequest, WithdrawalStatus
from .services import approve_influencer
from .tests import InfluencerTestBase


def _mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class RePostulacionTests(InfluencerTestBase):
    def _postular(self, codigo='NUEVOCODIGO'):
        self.client.force_login(self.afiliado_user)
        return self.client.post(reverse('influencer_suscribete'), {'accept_terms': '1', 'referral_code': codigo})

    def test_quien_se_dio_de_baja_puede_volver_a_postularse_con_otro_codigo(self):
        perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('influencer_quitar_suscripcion'))

        respuesta = self._postular('REGRESO2026')

        self.assertRedirects(respuesta, reverse('influencer_dashboard'), fetch_redirect_response=False)
        perfil.refresh_from_db()
        self.assertTrue(perfil.is_active)
        self.assertEqual(perfil.status, InfluencerStatus.PENDING)
        self.assertEqual(perfil.referral_code, 'REGRESO2026')
        self.assertIsNone(perfil.reviewed_at)
        self.assertIn('enviada de nuevo', _mensajes(respuesta)[-1])

    def test_un_rechazado_puede_postularse_otra_vez(self):
        perfil = InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.REJECTED)

        respuesta = self._postular('SEGUNDAVEZ')

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, InfluencerStatus.PENDING)
        self.assertEqual(perfil.referral_code, 'SEGUNDAVEZ')
        self.assertIn('enviada de nuevo', _mensajes(respuesta)[-1])

    def test_enviar_la_solicitud_dos_veces_no_la_duplica(self):
        InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.PENDING)

        respuesta = self._postular()

        self.assertEqual(InfluencerProfile.objects.filter(user=self.afiliado_user).count(), 1)
        self.assertIn('en revision', _mensajes(respuesta)[-1])

    def test_un_aprobado_que_reenvia_el_formulario_solo_recibe_un_aviso(self):
        perfil = self._crear_perfil_aprobado()
        codigo = perfil.referral_code

        respuesta = self._postular('OTROCODIGO')

        perfil.refresh_from_db()
        self.assertEqual(perfil.referral_code, codigo)
        self.assertIn('Ya eres influencer', _mensajes(respuesta)[-1])

    def test_el_propio_codigo_no_cuenta_como_ocupado_al_re_postularse(self):
        perfil = InfluencerProfile.objects.create(
            user=self.afiliado_user, status=InfluencerStatus.REJECTED, referral_code='MISMOCODIGO',
        )

        self._postular('MISMOCODIGO')

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, InfluencerStatus.PENDING)

    def test_un_codigo_que_ya_es_cupon_de_otro_se_rechaza(self):
        otro = InfluencerProfile.objects.create(
            user=self.comprador, status=InfluencerStatus.PENDING, referral_code='CUPONAJENO',
        )
        approve_influencer(otro, self.admin)

        respuesta = self._postular('CUPONAJENO')

        self.assertFalse(InfluencerProfile.objects.filter(user=self.afiliado_user).exists())
        self.assertIn('ya esta en uso', _mensajes(respuesta)[-1])

    def test_un_error_de_base_de_datos_al_crear_el_perfil_se_informa_sin_romper(self):
        with patch('influencer.views.InfluencerProfile.objects.create', side_effect=IntegrityError):
            respuesta = self._postular()

        self.assertRedirects(respuesta, reverse('influencer_dashboard'), fetch_redirect_response=False)
        self.assertIn('Hubo un problema', _mensajes(respuesta)[-1])


class AccesoSinPerfilTests(InfluencerTestBase):
    def setUp(self):
        self.client.force_login(self.afiliado_user)

    def test_el_panel_sin_perfil_lleva_al_formulario(self):
        self.assertRedirects(self.client.get(reverse('influencer_dashboard')), reverse('influencer_suscribete'))

    def test_compras_referidas_exige_ser_afiliado_aprobado(self):
        InfluencerProfile.objects.create(user=self.afiliado_user, status=InfluencerStatus.PENDING)
        self.assertRedirects(
            self.client.get(reverse('influencer_compras_referidas')), reverse('influencer_dashboard'),
            fetch_redirect_response=False,
        )

    def test_solicitar_comision_exige_ser_afiliado_aprobado(self):
        respuesta = self.client.post(reverse('influencer_solicitar_retiro'), {'payment_details': 'x'})
        self.assertRedirects(respuesta, reverse('influencer_dashboard'), fetch_redirect_response=False)
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_quitar_suscripcion_sin_perfil_solo_vuelve_a_la_portada(self):
        respuesta = self.client.post(reverse('influencer_quitar_suscripcion'))
        self.assertRedirects(respuesta, '/', fetch_redirect_response=False)


class SolicitarComisionTests(InfluencerTestBase):
    def setUp(self):
        self.perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)
        self.url = reverse('influencer_solicitar_retiro')

    def test_un_get_no_hace_nada(self):
        self.assertRedirects(self.client.get(self.url), reverse('influencer_dashboard'), fetch_redirect_response=False)

    def test_sin_datos_de_pago_se_pide_completarlos(self):
        respuesta = self.client.post(self.url, {'payment_details': '   '})
        self.assertIn('numero de cuenta', _mensajes(respuesta)[-1])
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_un_mensaje_demasiado_largo_se_rechaza(self):
        respuesta = self.client.post(self.url, {'payment_details': 'x' * 1001})
        self.assertIn('muy largo', _mensajes(respuesta)[-1])
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_sin_comisiones_disponibles_se_avisa(self):
        respuesta = self.client.post(self.url, {'payment_details': 'Cuenta 123'})
        self.assertIn('No tienes comisiones disponibles', _mensajes(respuesta)[-1])

    def test_con_saldo_se_crea_la_solicitud_y_una_segunda_se_bloquea(self):
        self._pedido_entregado(self.perfil)

        primera = self.client.post(self.url, {'payment_details': 'Cuenta 123'})
        self.assertIn('enviada', _mensajes(primera)[-1])
        self.assertEqual(WithdrawalRequest.objects.filter(status=WithdrawalStatus.PENDING).count(), 1)

        segunda = self.client.post(self.url, {'payment_details': 'Cuenta 123'})
        self.assertIn('ya tienes una solicitud', _mensajes(segunda)[-1].lower())
        self.assertEqual(WithdrawalRequest.objects.count(), 1)


class PanelConEstadisticasTests(InfluencerTestBase):
    def test_el_panel_calcula_la_conversion_cuando_hay_clics(self):
        perfil = self._crear_perfil_aprobado()
        perfil.referral_clicks.create()
        perfil.referral_clicks.create()
        perfil.total_referred = 1
        perfil.save(update_fields=['total_referred'])
        self.client.force_login(self.afiliado_user)

        respuesta = self.client.get(reverse('influencer_dashboard'))

        self.assertEqual(respuesta.context['click_count'], 2)
        self.assertEqual(respuesta.context['conversion_rate'], '50.0')
