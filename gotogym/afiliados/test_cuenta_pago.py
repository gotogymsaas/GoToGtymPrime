"""Inscripcion de la cuenta Bre-B del afiliado: acceso, campos obligatorios,
aceptacion de terminos y tratamiento de datos, reconocimiento de la llave y
visibilidad de los datos."""
from django.urls import reverse

from .forms import PayoutAccountForm
from .models import EstadoAfiliado, PayoutAccount, PerfilAfiliado
from .tests import AfiliadoTestBase

DATOS_VALIDOS = {
    'first_name': 'Ana',
    'last_name': 'Perez',
    'phone': '300 123 4567',
    'address': 'Calle 1 # 2-3, Bogota',
    'document_type': 'CC',
    'document_number': '1.020.304.050',
    'breb_key': '+57 300 123 4567',
    'accept_terms': 'on',
    'accept_data': 'on',
}


class AccesoCuentaDePagoTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('afiliado_cuenta_pago')

    def test_exige_iniciar_sesion(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_sin_perfil_de_afiliado_lleva_al_panel(self):
        self.client.force_login(self.afiliado_user)
        self.assertRedirects(self.client.get(self.url), reverse('afiliado_dashboard'), fetch_redirect_response=False)

    def test_un_afiliado_pendiente_todavia_no_puede_inscribirla(self):
        PerfilAfiliado.objects.create(user=self.afiliado_user, status=EstadoAfiliado.PENDING)
        self.client.force_login(self.afiliado_user)
        self.assertRedirects(self.client.get(self.url), reverse('afiliado_dashboard'), fetch_redirect_response=False)
        self.client.post(self.url, DATOS_VALIDOS)
        self.assertFalse(PayoutAccount.objects.exists())


class InscribirCuentaTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)
        self.url = reverse('afiliado_cuenta_pago')

    def test_el_formulario_trae_el_desplegable_de_tipos_de_documento(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, '<select name="document_type"')
        for etiqueta in ('Cedula de ciudadania', 'Cedula de extranjeria', 'NIT', 'Pasaporte'):
            self.assertContains(respuesta, etiqueta)
        self.assertContains(respuesta, 'name="document_number"')

    def test_precarga_nombre_y_telefono_del_perfil(self):
        self.afiliado_user.first_name, self.afiliado_user.last_name = 'Laura', 'Gomez'
        self.afiliado_user.phone = '3105550000'
        self.afiliado_user.save()
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="Laura"')
        self.assertContains(respuesta, 'value="Gomez"')
        self.assertContains(respuesta, 'value="3105550000"')

    def test_guarda_la_cuenta_normalizando_documento_y_llave(self):
        respuesta = self.client.post(self.url, DATOS_VALIDOS)
        self.assertRedirects(respuesta, reverse('afiliado_dashboard'), fetch_redirect_response=False)
        cuenta = PayoutAccount.objects.get(afiliado=self.perfil)
        self.assertEqual(cuenta.document_number, '1020304050')
        self.assertEqual(cuenta.breb_key, '3001234567')
        self.assertEqual(cuenta.full_name, 'Ana Perez')

    def test_el_formulario_no_pregunta_el_tipo_de_llave_ni_trae_la_intro(self):
        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, 'breb_key_type')
        self.assertNotContains(respuesta, 'Tipo de llave')
        self.assertNotContains(respuesta, 'Qu&eacute; es Bre-B')
        self.assertContains(respuesta, 'aseg&uacute;rate de incluir el @')

    def test_ofrece_las_casillas_de_terminos_y_datos_antes_de_los_campos(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('name="accept_terms"', html)
        self.assertIn('name="accept_data"', html)
        self.assertLess(html.index('name="accept_data"'), html.index('name="first_name"'))

    def test_sin_aceptar_terminos_o_datos_no_se_guarda(self):
        for casilla in ('accept_terms', 'accept_data'):
            with self.subTest(casilla=casilla):
                datos = {k: v for k, v in DATOS_VALIDOS.items() if k != casilla}
                respuesta = self.client.post(self.url, datos)
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(casilla, respuesta.context['form'].errors)
                self.assertFalse(PayoutAccount.objects.exists())

    def test_registra_cuando_se_aceptaron_terminos_y_datos(self):
        self.client.post(self.url, DATOS_VALIDOS)
        cuenta = PayoutAccount.objects.get()
        self.assertIsNotNone(cuenta.terms_accepted_at)
        self.assertIsNotNone(cuenta.data_consent_at)

    def test_reinscribir_actualiza_la_misma_cuenta(self):
        self.client.post(self.url, DATOS_VALIDOS)
        self.client.post(self.url, {**DATOS_VALIDOS, 'first_name': 'Maria'})
        self.assertEqual(PayoutAccount.objects.count(), 1)
        self.assertEqual(PayoutAccount.objects.get().first_name, 'Maria')

    def test_cada_campo_es_obligatorio(self):
        for campo in DATOS_VALIDOS:
            with self.subTest(campo=campo):
                respuesta = self.client.post(self.url, {**DATOS_VALIDOS, campo: ''})
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo, respuesta.context['form'].errors)
        self.assertFalse(PayoutAccount.objects.exists())

    def test_un_tipo_de_documento_fuera_del_catalogo_se_rechaza(self):
        respuesta = self.client.post(self.url, {**DATOS_VALIDOS, 'document_type': 'XX'})
        self.assertIn('document_type', respuesta.context['form'].errors)

    def test_el_panel_muestra_la_cuenta_inscrita(self):
        self.client.post(self.url, DATOS_VALIDOS)
        respuesta = self.client.get(reverse('afiliado_dashboard'))
        self.assertContains(respuesta, 'Cuenta Bre-B para tus pagos')
        self.assertContains(respuesta, 'Ana Perez')
        self.assertContains(respuesta, 'Editar cuenta')

    def test_el_panel_sin_cuenta_invita_a_inscribirla(self):
        respuesta = self.client.get(reverse('afiliado_dashboard'))
        self.assertContains(respuesta, 'Inscribir cuenta Bre-B')


class ValidacionDeLlaveTests(AfiliadoTestBase):
    """La llave se reconoce por su forma: el afiliado no indica de que tipo es."""

    def _formulario(self, llave):
        formulario = PayoutAccountForm({**DATOS_VALIDOS, 'breb_key': llave})
        formulario.is_valid()
        return formulario

    def test_celular_en_distintos_formatos_se_guarda_igual(self):
        for llave in ('3001234567', '300 123 4567', '+57 3001234567', '573001234567'):
            with self.subTest(llave=llave):
                formulario = self._formulario(llave)
                self.assertNotIn('breb_key', formulario.errors)
                self.assertEqual(formulario.cleaned_data['breb_key'], '3001234567')

    def test_documento_como_llave(self):
        formulario = self._formulario('1.020.304.050')
        self.assertEqual(formulario.cleaned_data['breb_key'], '1020304050')

    def test_correo_se_guarda_en_minusculas(self):
        self.assertEqual(self._formulario('Ana@Correo.COM').cleaned_data['breb_key'], 'ana@correo.com')
        self.assertIn('breb_key', self._formulario('ana@sin-punto@x').errors)

    def test_la_llave_con_arroba_se_conserva_tal_cual(self):
        self.assertEqual(self._formulario('@anafit26').cleaned_data['breb_key'], '@anafit26')
        self.assertIn('breb_key', self._formulario('@a b').errors)
        self.assertIn('breb_key', self._formulario('@ab').errors)

    def test_no_se_agrega_arroba_a_una_llave_sin_el(self):
        self.assertEqual(self._formulario('anafit26').cleaned_data['breb_key'], 'anafit26')

    def test_llaves_demasiado_cortas_o_con_simbolos_se_rechazan(self):
        for llave in ('12', 'ab#cd', 'no es una llave'):
            with self.subTest(llave=llave):
                self.assertIn('breb_key', self._formulario(llave).errors)

    def test_telefono_de_contacto_invalido(self):
        formulario = PayoutAccountForm({**DATOS_VALIDOS, 'phone': 'abc'})
        self.assertFalse(formulario.is_valid())
        self.assertIn('phone', formulario.errors)


class VistaAdminCuentaTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self._dar_permisos_de_admin(self.admin)
        self.perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.admin)
        self.url = reverse('admin_afiliado_detail', args=[self.perfil.pk])

    def test_sin_cuenta_el_admin_lo_ve_indicado(self):
        self.assertContains(self.client.get(self.url), 'todavia no inscribe su cuenta Bre-B')

    def test_con_cuenta_el_admin_ve_titular_documento_y_llave(self):
        self._inscribir_cuenta(self.perfil)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Ana Perez')
        self.assertContains(respuesta, 'Cedula de ciudadania')
        self.assertContains(respuesta, '1020304050')
        self.assertContains(respuesta, '3001234567')


class ActualizarCuentaTests(AfiliadoTestBase):
    """El medio de pago se actualiza como cualquier otro dato del afiliado."""

    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)
        self.url = reverse('afiliado_cuenta_pago')
        self.client.post(self.url, DATOS_VALIDOS)
        self.cuenta = PayoutAccount.objects.get()
        self.aceptado_el = self.cuenta.terms_accepted_at

    def _sin_aceptaciones(self, **cambios):
        datos = {k: v for k, v in DATOS_VALIDOS.items() if not k.startswith('accept_')}
        datos.update(cambios)
        return datos

    def test_actualizar_no_pide_aceptar_de_nuevo(self):
        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, 'name="accept_terms"')
        self.assertNotContains(respuesta, 'name="accept_data"')
        self.assertContains(respuesta, 'no tienes que volver a hacerlo')

    def test_cambia_la_llave_y_los_datos_sin_repetir_la_aceptacion(self):
        respuesta = self.client.post(self.url, self._sin_aceptaciones(
            breb_key='@nuevallave1', first_name='Maria', address='Carrera 9 # 8-7',
        ))
        self.assertRedirects(respuesta, reverse('afiliado_dashboard'), fetch_redirect_response=False)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.breb_key, '@nuevallave1')
        self.assertEqual(self.cuenta.first_name, 'Maria')
        self.assertEqual(self.cuenta.address, 'Carrera 9 # 8-7')

    def test_la_fecha_de_la_primera_aceptacion_se_conserva(self):
        self.client.post(self.url, self._sin_aceptaciones(first_name='Maria'))
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.terms_accepted_at, self.aceptado_el)

    def test_al_actualizar_los_datos_siguen_siendo_obligatorios_y_validados(self):
        respuesta = self.client.post(self.url, self._sin_aceptaciones(breb_key='no valida!'))
        self.assertIn('breb_key', respuesta.context['form'].errors)
        respuesta = self.client.post(self.url, self._sin_aceptaciones(document_number=''))
        self.assertIn('document_number', respuesta.context['form'].errors)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.breb_key, '3001234567')

    def test_quien_nunca_acepto_sigue_obligado_a_hacerlo(self):
        self.cuenta.terms_accepted_at = None
        self.cuenta.save()
        respuesta = self.client.post(self.url, self._sin_aceptaciones())
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('accept_terms', respuesta.context['form'].errors)

    def test_desde_mi_perfil_se_llega_a_editar_la_cuenta(self):
        respuesta = self.client.get(reverse('afiliado_editar_perfil'))
        self.assertContains(respuesta, 'Cuenta Bre-B para tus pagos')
        self.assertContains(respuesta, reverse('afiliado_cuenta_pago'))
        self.assertContains(respuesta, 'Editar cuenta Bre-B')

    def test_mi_perfil_invita_a_inscribirla_si_aun_no_existe(self):
        self.cuenta.delete()
        respuesta = self.client.get(reverse('afiliado_editar_perfil'))
        self.assertContains(respuesta, 'Inscribir cuenta Bre-B')

    def test_quien_espera_aprobacion_no_ve_la_cuenta_de_pago_en_su_perfil(self):
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(status=EstadoAfiliado.PENDING)
        respuesta = self.client.get(reverse('afiliado_editar_perfil'))
        self.assertNotContains(respuesta, 'Cuenta Bre-B para tus pagos')
