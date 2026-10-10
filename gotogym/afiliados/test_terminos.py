"""Texto publico de los terminos del programa y registro de la version que
cada persona acepta al postularse."""
from django.urls import reverse

from .models import EstadoAfiliado, PerfilAfiliado
from .terminos import VERSION_TERMINOS_AFILIADOS
from .tests import AfiliadoTestBase, datos_postulacion


class PaginaDeTerminosTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.respuesta = self.client.get(reverse('afiliado_terminos'))
        self.html = self.respuesta.content.decode()

    def test_es_publica_y_muestra_la_version_vigente(self):
        self.assertEqual(self.respuesta.status_code, 200)
        self.assertContains(self.respuesta, f'Versión {VERSION_TERMINOS_AFILIADOS}')

    def test_identifica_a_la_empresa_y_al_soporte(self):
        self.assertContains(self.respuesta, 'Friends N Gifts S.A.S.')
        self.assertContains(self.respuesta, 'support@gotogym.store')

    def test_fija_la_comision_y_el_periodo_de_validacion(self):
        self.assertContains(self.respuesta, '20 %')
        self.assertContains(self.respuesta, '5 días hábiles después de la entrega')
        self.assertNotIn('15 días calendario desde', self.html)

    def test_el_unico_medio_de_pago_es_bre_b(self):
        self.assertContains(self.respuesta, 'Bre-B')
        for ausente in ('Nequi', 'crédito en la tienda', 'retenciones'):
            with self.subTest(ausente=ausente):
                self.assertNotIn(ausente, self.html)

    def test_el_programa_se_llama_afiliados_y_no_incluye_restos_de_otras_fuentes(self):
        for ausente in ('Embajador', 'embajador', 'Influencer GoToGym', 'okolo', 'blindcreator'):
            with self.subTest(ausente=ausente):
                self.assertNotIn(ausente, self.html)

    def test_pide_ser_mayor_de_edad(self):
        self.assertContains(self.respuesta, 'mayor de edad (18 años o más)')

    def test_aparece_en_la_navegacion_legal_y_en_el_pie(self):
        url = reverse('afiliado_terminos')
        self.assertContains(self.respuesta, f'href="{url}" aria-current="page"')
        pie = self.client.get(reverse('home')).content.decode()
        self.assertIn(f'href="{url}"', pie)


class VersionAceptadaTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.afiliado_user)
        self.url = reverse('afiliado_suscribete')

    def test_el_formulario_enlaza_los_terminos_y_avisa_de_la_mayoria_de_edad(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, f'href="{reverse("afiliado_terminos")}"')
        self.assertContains(respuesta, 'mayor de 18 a')

    def test_no_agrega_otras_casillas_de_aceptacion(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.content.decode().count('type="checkbox"'), 1)

    def test_la_postulacion_guarda_la_version_aceptada(self):
        self.client.post(self.url, datos_postulacion())
        perfil = PerfilAfiliado.objects.get(user=self.afiliado_user)
        self.assertEqual(perfil.terms_version, VERSION_TERMINOS_AFILIADOS)
        self.assertIsNotNone(perfil.terms_accepted_at)

    def test_al_repostularse_se_registra_la_version_vigente(self):
        PerfilAfiliado.objects.create(
            user=self.afiliado_user, status=EstadoAfiliado.REJECTED, terms_version='0.9',
        )
        self.client.post(self.url, datos_postulacion())
        perfil = PerfilAfiliado.objects.get(user=self.afiliado_user)
        self.assertEqual(perfil.terms_version, VERSION_TERMINOS_AFILIADOS)

    def test_un_perfil_anterior_queda_sin_version(self):
        perfil = PerfilAfiliado.objects.create(user=self.afiliado_user, status=EstadoAfiliado.PENDING)
        self.assertEqual(perfil.terms_version, '')


class EnlacesAlTextoDeTerminosTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)
        self.url_terminos = reverse('afiliado_terminos')

    def test_la_cuenta_de_pago_apunta_a_los_terminos_del_programa(self):
        html = self.client.get(reverse('afiliado_cuenta_pago')).content.decode()
        # El pie del sitio conserva el enlace a los terminos de la tienda: lo
        # que importa es que el texto legal de la cuenta ya no lo use.
        self.assertIn(f'href="{self.url_terminos}" target="_blank"', html)
        self.assertNotIn(f'href="{reverse("terminos")}" target="_blank"', html)

    def test_el_enlace_para_compartir_usa_la_portada(self):
        perfil = PerfilAfiliado.objects.get(user=self.afiliado_user)
        html = self.client.get(reverse('afiliado_dashboard')).content.decode()
        self.assertIn(f'{reverse("home")}?ref={perfil.referral_code}</code>', html)
        self.assertNotIn(f'{reverse("tienda:producto_list")}?ref=', html)
