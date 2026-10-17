"""Postulacion al programa: datos personales obligatorios, redes sociales
dinamicas (Instagram por defecto, "Otra", varias filas), precarga y lo que ve
el equipo al revisar."""
from django.urls import reverse

from .models import EstadoAfiliado, PerfilAfiliado, SocialNetwork
from .tests import AfiliadoTestBase, datos_postulacion

CAMPOS_PERSONALES = ('first_name', 'last_name', 'phone', 'address', 'document_type', 'document_number')


def _con_redes(*redes, **cambios):
    """Postulacion valida con las redes dadas como (plataforma, otra, usuario, seguidores)."""
    datos = datos_postulacion(**cambios)
    for clave in [k for k in datos if k.startswith('redes-') and k[6].isdigit()]:
        del datos[clave]
    datos['redes-TOTAL_FORMS'] = str(len(redes))
    for i, (plataforma, otra, usuario, seguidores) in enumerate(redes):
        datos.update({
            f'redes-{i}-platform': plataforma, f'redes-{i}-other_name': otra,
            f'redes-{i}-username': usuario, f'redes-{i}-followers': seguidores,
        })
    return datos


class FormularioDePostulacionTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.afiliado_user)
        self.url = reverse('afiliado_suscribete')

    def test_pide_los_datos_personales_con_desplegable_de_documento(self):
        respuesta = self.client.get(self.url)
        for campo in CAMPOS_PERSONALES:
            self.assertContains(respuesta, f'name="{campo}"')
        self.assertContains(respuesta, '<select name="document_type"')
        self.assertContains(respuesta, 'Cédula de ciudadanía')

    def test_instagram_viene_por_defecto_y_el_desplegable_ofrece_otras_redes(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, '<select name="redes-0-platform"')
        self.assertContains(respuesta, '<option value="instagram" selected>')
        for red in ('TikTok', 'YouTube', 'Facebook', 'Otra'):
            self.assertContains(respuesta, f'>{red}</option>')
        self.assertContains(respuesta, 'name="redes-0-username"')
        self.assertContains(respuesta, 'name="redes-0-followers"')

    def test_trae_la_plantilla_para_agregar_mas_redes(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'id="agregar-red"')
        self.assertContains(respuesta, 'redes-__prefix__-platform')

    def test_precarga_nombre_y_telefono_de_la_cuenta(self):
        self.afiliado_user.first_name, self.afiliado_user.last_name = 'Laura', 'Gomez'
        self.afiliado_user.phone = '3105550000'
        self.afiliado_user.save()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="Laura"')
        self.assertContains(respuesta, 'value="3105550000"')

    def test_no_precarga_el_codigo_aleatorio_del_modelo(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'name="referral_code"')
        self.assertFalse(respuesta.context['form']['referral_code'].value())


class EnviarPostulacionTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.afiliado_user)
        self.url = reverse('afiliado_suscribete')

    def _enviar(self, datos):
        return self.client.post(self.url, datos)

    def test_guarda_datos_personales_y_redes_en_un_perfil_pendiente(self):
        respuesta = self._enviar(_con_redes(
            ('instagram', '', '@AnaFit', '1200'), ('tiktok', '', 'ana.fit', '8500'),
        ))
        self.assertRedirects(respuesta, reverse('afiliado_dashboard'), fetch_redirect_response=False)
        perfil = PerfilAfiliado.objects.get(user=self.afiliado_user)
        self.assertEqual(perfil.status, EstadoAfiliado.PENDING)
        self.assertEqual(perfil.full_name, 'Ana Perez')
        self.assertEqual(perfil.document_type, 'CC')
        self.assertEqual(perfil.document_number, '1020304050')
        self.assertEqual(
            list(perfil.social_networks.values_list('platform', 'username', 'followers')),
            [('instagram', 'AnaFit', 1200), ('tiktok', 'ana.fit', 8500)],
        )

    def test_cada_dato_personal_es_obligatorio(self):
        for campo in CAMPOS_PERSONALES:
            with self.subTest(campo=campo):
                respuesta = self._enviar(datos_postulacion(**{campo: ''}))
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo, respuesta.context['form'].errors)
        self.assertFalse(PerfilAfiliado.objects.exists())

    def test_los_errores_conservan_lo_que_la_persona_ya_escribio(self):
        respuesta = self._enviar(datos_postulacion(document_number=''))
        self.assertContains(respuesta, 'value="Ana"')
        self.assertContains(respuesta, 'value="anafit"')
        self.assertContains(respuesta, 'value="1200"')

    def test_exige_al_menos_una_red(self):
        respuesta = self._enviar(_con_redes())
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('al menos una red', ' '.join(respuesta.context['redes'].non_form_errors()))
        self.assertFalse(PerfilAfiliado.objects.exists())

    def test_la_primera_red_exige_usuario_y_seguidores(self):
        for campo in ('username', 'followers'):
            with self.subTest(campo=campo):
                datos = datos_postulacion(**{f'redes-0-{campo}': ''})
                respuesta = self._enviar(datos)
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo, respuesta.context['redes'].forms[0].errors)
        self.assertFalse(PerfilAfiliado.objects.exists())

    def test_una_fila_extra_en_blanco_se_ignora(self):
        datos = _con_redes(('instagram', '', 'anafit', '10'), ('instagram', '', '', ''))
        self._enviar(datos)
        self.assertEqual(SocialNetwork.objects.count(), 1)

    def test_otra_red_exige_su_nombre(self):
        respuesta = self._enviar(_con_redes(('other', '', 'ana', '10')))
        self.assertIn('other_name', respuesta.context['redes'].forms[0].errors)
        self._enviar(_con_redes(('other', 'Kwai', 'ana', '10')))
        red = SocialNetwork.objects.get()
        self.assertEqual(red.platform_label, 'Kwai')

    def test_el_nombre_de_otra_red_se_descarta_si_la_red_es_conocida(self):
        self._enviar(_con_redes(('youtube', 'Kwai', 'ana', '10')))
        self.assertEqual(SocialNetwork.objects.get().other_name, '')

    def test_el_usuario_no_admite_enlaces_ni_espacios(self):
        for usuario in ('https://instagram.com/ana', 'ana fit', 'a'):
            with self.subTest(usuario=usuario):
                respuesta = self._enviar(_con_redes(('instagram', '', usuario, '10')))
                self.assertIn('username', respuesta.context['redes'].forms[0].errors)

    def test_seguidores_no_puede_ser_negativo_ni_texto(self):
        for valor in ('-5', 'mucho'):
            with self.subTest(valor=valor):
                respuesta = self._enviar(_con_redes(('instagram', '', 'ana', valor)))
                self.assertIn('followers', respuesta.context['redes'].forms[0].errors)

    def test_seguidores_acepta_puntos_de_mil(self):
        self._enviar(_con_redes(('instagram', '', 'ana', '1.250.000')))
        self.assertEqual(SocialNetwork.objects.get().followers, 1250000)

    def test_el_campo_de_seguidores_es_texto_para_admitir_los_puntos(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'type="text" name="redes-0-followers"')
        self.assertContains(respuesta, 'data-miles')

    def test_la_misma_red_con_el_mismo_usuario_no_se_repite(self):
        respuesta = self._enviar(_con_redes(('instagram', '', 'Ana', '10'), ('instagram', '', 'ana', '20')))
        self.assertIn('repetida', ' '.join(respuesta.context['redes'].non_form_errors()))
        self.assertFalse(PerfilAfiliado.objects.exists())

    def test_la_misma_red_con_otro_usuario_si_se_admite(self):
        self._enviar(_con_redes(('instagram', '', 'ana', '10'), ('instagram', '', 'ana.fit', '20')))
        self.assertEqual(SocialNetwork.objects.count(), 2)

    def test_sin_aceptar_terminos_no_se_guarda_nada(self):
        datos = datos_postulacion()
        del datos['accept_terms']
        respuesta = self._enviar(datos)
        self.assertIn('accept_terms', respuesta.context['form'].errors)
        self.assertFalse(PerfilAfiliado.objects.exists())

    def test_sin_el_formulario_de_redes_no_hay_error_500(self):
        datos = {k: v for k, v in datos_postulacion().items() if not k.startswith('redes-')}
        respuesta = self._enviar(datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(PerfilAfiliado.objects.exists())


class RePostulacionConRedesTests(AfiliadoTestBase):
    def test_al_repostularse_las_redes_se_reemplazan_y_se_precargan_las_anteriores(self):
        perfil = PerfilAfiliado.objects.create(
            user=self.afiliado_user, status=EstadoAfiliado.REJECTED, first_name='Ana', last_name='Perez',
            phone='3001234567', address='Calle 1', document_type='CC', document_number='1020304050',
        )
        perfil.social_networks.create(platform='tiktok', username='vieja', followers=15000)
        self.client.force_login(self.afiliado_user)

        respuesta = self.client.get(reverse('afiliado_suscribete'))
        self.assertContains(respuesta, 'value="vieja"')
        self.assertContains(respuesta, 'value="15.000"')
        self.assertContains(respuesta, 'value="1020304050"')

        self.client.post(reverse('afiliado_suscribete'), _con_redes(('youtube', '', 'nueva', '99'), codigo='OTRO1234'))
        perfil.refresh_from_db()
        self.assertEqual(perfil.status, EstadoAfiliado.PENDING)
        self.assertEqual(list(perfil.social_networks.values_list('username', flat=True)), ['nueva'])


class VistaAdminPostulacionTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.afiliado_user)
        self.client.post(
            reverse('afiliado_suscribete'),
            _con_redes(('instagram', '', 'anafit', '1200'), ('other', 'Kwai', 'ana_k', '300')),
        )
        self.perfil = PerfilAfiliado.objects.get(user=self.afiliado_user)
        self.client.force_login(self.admin)

    def test_el_admin_ve_datos_personales_redes_y_total(self):
        respuesta = self.client.get(reverse('admin_afiliado_detail', args=[self.perfil.pk]))
        self.assertContains(respuesta, 'Ana Perez')
        self.assertContains(respuesta, 'Cédula de ciudadanía')
        self.assertContains(respuesta, '@anafit')
        self.assertContains(respuesta, 'Kwai')
        self.assertContains(respuesta, '1.500')

    def test_un_perfil_anterior_sin_datos_lo_indica(self):
        antiguo = PerfilAfiliado.objects.create(user=self.comprador, status=EstadoAfiliado.PENDING)
        respuesta = self.client.get(reverse('admin_afiliado_detail', args=[antiguo.pk]))
        self.assertContains(respuesta, 'antes de que se pidieran sus datos personales')
        self.assertContains(respuesta, 'no declaro redes sociales')


class CuentaDePagoReutilizaLosDatosTests(AfiliadoTestBase):
    def test_la_cuenta_bre_b_precarga_los_datos_de_la_postulacion(self):
        self.client.force_login(self.afiliado_user)
        self.client.post(reverse('afiliado_suscribete'), datos_postulacion())
        perfil = PerfilAfiliado.objects.get(user=self.afiliado_user)
        from .services import approve_afiliado
        approve_afiliado(perfil, self.admin)

        respuesta = self.client.get(reverse('afiliado_cuenta_pago'))
        self.assertContains(respuesta, 'value="1020304050"')
        self.assertContains(respuesta, 'value="Calle 1 # 2-3, Bogota"')
        self.assertContains(respuesta, '<option value="CC" selected>')
