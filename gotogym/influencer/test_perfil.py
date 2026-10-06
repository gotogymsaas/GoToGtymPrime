"""Inicio del afiliado (resumen de redes y datos personales), edicion del
perfil y la ruta /afiliados/ que reemplaza a /influencer/."""
from django.urls import reverse

from .models import InfluencerProfile, InfluencerStatus, SocialNetwork
from .test_postulacion import _con_redes
from .tests import InfluencerTestBase, datos_postulacion


def _datos_perfil(**cambios):
    """Formulario de edicion valido: los datos personales y una red."""
    datos = {k: v for k, v in datos_postulacion().items() if k not in ('referral_code', 'accept_terms')}
    datos.update(cambios)
    return datos


class RutaDeAfiliadosTests(InfluencerTestBase):
    def test_el_panel_vive_en_afiliados(self):
        self.assertEqual(reverse('influencer_dashboard'), '/es/afiliados/dashboard/')

    def test_la_ruta_antigua_redirige_conservando_la_consulta(self):
        respuesta = self.client.get('/es/influencer/dashboard/?x=1')
        self.assertEqual(respuesta.status_code, 301)
        self.assertEqual(respuesta['Location'], '/es/afiliados/dashboard/?x=1')

    def test_la_raiz_antigua_tambien_redirige(self):
        respuesta = self.client.get('/en/influencer/')
        self.assertEqual(respuesta.status_code, 301)
        self.assertEqual(respuesta['Location'], '/en/afiliados/')

    def test_robots_excluye_la_ruta_nueva(self):
        self.assertIn('Disallow: /es/afiliados/', self.client.get('/robots.txt').content.decode())


class InicioDelAfiliadoTests(InfluencerTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)

    def test_sin_redes_ni_datos_invita_a_completarlos(self):
        respuesta = self.client.get(reverse('influencer_dashboard'))
        self.assertContains(respuesta, 'Agregar redes')
        self.assertContains(respuesta, 'Completar mi perfil')

    def test_muestra_el_resumen_de_redes_con_el_total(self):
        self.perfil.social_networks.create(platform='instagram', username='anafit', followers=1200)
        self.perfil.social_networks.create(platform='other', other_name='Kwai', username='ana_k', followers=300)
        respuesta = self.client.get(reverse('influencer_dashboard'))
        self.assertContains(respuesta, '2 redes')
        self.assertContains(respuesta, '1.500 seguidores en total')
        self.assertContains(respuesta, '@anafit &middot; 1.200 seguidores', html=False)
        self.assertContains(respuesta, 'Kwai')
        self.assertContains(respuesta, 'Editar redes')

    def test_muestra_los_datos_personales_y_el_acceso_a_editarlos(self):
        InfluencerProfile.objects.filter(pk=self.perfil.pk).update(
            first_name='Ana', last_name='Perez', phone='3001234567', address='Calle 1',
            document_type='CC', document_number='1020304050',
        )
        respuesta = self.client.get(reverse('influencer_dashboard'))
        self.assertContains(respuesta, 'Ana Perez')
        self.assertContains(respuesta, 'Cedula de ciudadania')
        self.assertContains(respuesta, 'Editar mi perfil')
        self.assertContains(respuesta, reverse('influencer_editar_perfil'))

    def test_quien_espera_revision_tambien_puede_editar_su_perfil(self):
        InfluencerProfile.objects.filter(pk=self.perfil.pk).update(status=InfluencerStatus.PENDING)
        respuesta = self.client.get(reverse('influencer_dashboard'))
        self.assertContains(respuesta, 'Editar mi perfil')
        self.assertContains(respuesta, 'Cancelar solicitud')


class EditarPerfilTests(InfluencerTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('influencer_suscribete'), _con_redes(('instagram', '', 'anafit', '1200')))
        self.perfil = InfluencerProfile.objects.get(user=self.afiliado_user)
        self.url = reverse('influencer_editar_perfil')

    def test_precarga_datos_y_redes_actuales(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="Ana"')
        self.assertContains(respuesta, 'value="1020304050"')
        self.assertContains(respuesta, 'value="anafit"')
        self.assertContains(respuesta, 'value="1.200"')
        self.assertContains(respuesta, 'id="agregar-red"')
        self.assertNotContains(respuesta, 'name="referral_code"')

    def test_actualiza_datos_y_reemplaza_las_redes(self):
        datos = _con_redes(('tiktok', '', 'ana.fit', '9.000'), ('youtube', '', 'anacanal', '500'))
        datos = {k: v for k, v in datos.items() if k not in ('referral_code', 'accept_terms')}
        datos.update(phone='3109999999', address='Carrera 7 # 8-9')

        respuesta = self.client.post(self.url, datos)

        self.assertRedirects(respuesta, reverse('influencer_dashboard'), fetch_redirect_response=False)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.phone, '3109999999')
        self.assertEqual(self.perfil.address, 'Carrera 7 # 8-9')
        self.assertEqual(
            list(self.perfil.social_networks.values_list('platform', 'username', 'followers')),
            [('tiktok', 'ana.fit', 9000), ('youtube', 'anacanal', 500)],
        )

    def test_editar_no_cambia_el_estado_ni_el_codigo(self):
        codigo, estado = self.perfil.referral_code, self.perfil.status
        self.client.post(self.url, _datos_perfil(first_name='Maria'))
        self.perfil.refresh_from_db()
        self.assertEqual((self.perfil.referral_code, self.perfil.status), (codigo, estado))
        self.assertEqual(self.perfil.first_name, 'Maria')

    def test_con_errores_no_guarda_nada(self):
        respuesta = self.client.post(self.url, _datos_perfil(document_number='', **{'redes-0-username': 'a b'}))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('document_number', respuesta.context['form'].errors)
        self.assertIn('username', respuesta.context['redes'].forms[0].errors)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.document_number, '1020304050')
        self.assertEqual(list(SocialNetwork.objects.values_list('username', flat=True)), ['anafit'])

    def test_sin_perfil_o_dado_de_baja_lleva_al_panel(self):
        self.client.post(reverse('influencer_quitar_suscripcion'))
        self.assertRedirects(self.client.get(self.url), reverse('influencer_dashboard'), fetch_redirect_response=False)
        self.client.force_login(self.comprador)
        self.assertRedirects(self.client.get(self.url), reverse('influencer_dashboard'), fetch_redirect_response=False)
