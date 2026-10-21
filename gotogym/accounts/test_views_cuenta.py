"""Login, registro y edicion de perfil: ramas de error y de exito."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

CLAVE = 'Clave-Segura-123'


def _usuario(email='cuenta@example.com', **extra):
    User = get_user_model()
    return User.objects.create_user(email=email, username=email, password=CLAVE, **extra)


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = _usuario(first_name='Ana')
        self.url = reverse('commercial_login')

    def test_pagina_de_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_login_correcto_entra_a_la_home(self):
        respuesta = self.client.post(self.url, {'username': 'cuenta@example.com', 'password': CLAVE})
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)
        self.assertIn('_auth_user_id', self.client.session)

    def test_acepta_el_nombre_de_usuario_sin_importar_mayusculas(self):
        respuesta = self.client.post(self.url, {'username': 'CUENTA@example.com', 'password': CLAVE})
        self.assertEqual(respuesta.status_code, 302)

    def test_login_con_clave_incorrecta_muestra_un_error_generico(self):
        respuesta = self.client.post(self.url, {'username': 'cuenta@example.com', 'password': 'otra'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['error_message'], 'Credenciales incorrectas')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_un_usuario_inexistente_recibe_el_mismo_error(self):
        respuesta = self.client.post(self.url, {'username': 'nadie@example.com', 'password': CLAVE})
        self.assertEqual(respuesta.context['error_message'], 'Credenciales incorrectas')

    def test_un_usuario_inactivo_no_entra(self):
        get_user_model().objects.filter(pk=self.usuario.pk).update(is_active=False)
        respuesta = self.client.post(self.url, {'username': 'cuenta@example.com', 'password': CLAVE})
        self.assertEqual(respuesta.context['error_message'], 'Credenciales incorrectas')

    def test_respeta_next_del_mismo_sitio(self):
        destino = reverse('tienda:producto_list')
        respuesta = self.client.post(self.url, {
            'username': 'cuenta@example.com', 'password': CLAVE, 'next': destino,
        })
        self.assertRedirects(respuesta, destino, fetch_redirect_response=False)

    def test_ignora_un_next_hacia_otro_sitio(self):
        respuesta = self.client.post(self.url, {
            'username': 'cuenta@example.com', 'password': CLAVE, 'next': 'https://malo.example.com/',
        })
        self.assertRedirects(respuesta, '/', fetch_redirect_response=False)

    def test_la_ruta_login_usa_la_misma_pantalla(self):
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)


class RegistroTests(TestCase):
    DATOS = {
        'first_name': 'Luis', 'last_name': 'Soto', 'age': '28', 'email': 'luis@example.com',
        'password1': CLAVE, 'password2': CLAVE, 'accepted_terms': 'on',
    }

    def _mensajes(self, respuesta):
        return [str(m) for m in respuesta.context['messages']]

    def test_pagina_de_registro(self):
        self.assertEqual(self.client.get(reverse('register')).status_code, 200)

    def test_campos_obligatorios(self):
        respuesta = self.client.post(reverse('register'), {**self.DATOS, 'first_name': ''})
        self.assertIn('Completa tu nombre, correo y contraseña, y acepta los términos.', self._mensajes(respuesta))
        self.assertFalse(get_user_model().objects.filter(email='luis@example.com').exists())

    def test_debe_aceptar_los_terminos(self):
        datos = {k: v for k, v in self.DATOS.items() if k != 'accepted_terms'}
        respuesta = self.client.post(reverse('register'), datos)
        self.assertIn('Completa tu nombre, correo y contraseña, y acepta los términos.', self._mensajes(respuesta))

    def test_las_contrasenas_deben_coincidir(self):
        respuesta = self.client.post(reverse('register'), {**self.DATOS, 'password2': 'distinta'})
        self.assertIn('Las contraseñas no coinciden.', self._mensajes(respuesta))

    def test_correo_ya_registrado(self):
        _usuario('luis@example.com')
        respuesta = self.client.post(reverse('register'), self.DATOS)
        self.assertIn('El correo ya está registrado.', self._mensajes(respuesta))

    def test_registro_correcto_guarda_la_aceptacion_de_terminos(self):
        self.client.post(reverse('register'), self.DATOS)
        usuario = get_user_model().objects.get(email='luis@example.com')
        self.assertTrue(usuario.accepted_terms)
        self.assertIsNotNone(usuario.terms_accepted_at)
        self.assertEqual(len(usuario.terms_hash), 128)


class EditarPerfilTests(TestCase):
    def setUp(self):
        self.usuario = _usuario(first_name='Ana', last_name='Marin', age=30)
        self.client.force_login(self.usuario)
        self.url = reverse('edit_profile')

    def _post(self, **datos):
        return self.client.post(self.url, datos)

    def _ajax(self, **datos):
        return self.client.post(self.url, datos, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def _refrescar(self):
        self.usuario.refresh_from_db()
        return self.usuario

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_muestra_el_formulario(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('address_form', respuesta.context)

    def test_actualiza_nombre_apellido_telefono_y_edad(self):
        respuesta = self._post(first_name='Anita', last_name='Mar', phone='3001112233', age='31')
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)
        usuario = self._refrescar()
        self.assertEqual((usuario.first_name, usuario.last_name), ('Anita', 'Mar'))
        self.assertEqual((usuario.phone, usuario.age), ('3001112233', 31))

    def test_guarda_el_documento_sin_formato(self):
        respuesta = self._post(document_type='CC', document_number='1.020.304.050')
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)
        usuario = self._refrescar()
        self.assertEqual((usuario.document_type, usuario.document_number), ('CC', '1020304050'))

    def test_un_nit_se_guarda_sin_digito_de_verificacion(self):
        self._post(document_type='NIT', document_number='900.123.456-8')
        self.assertEqual(self._refrescar().document_number, '900123456')

    def test_un_documento_invalido_no_se_guarda(self):
        respuesta = self._ajax(document_type='CC', document_number='12AB5')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self._refrescar().document_number, '')

    def test_numero_sin_tipo_no_se_guarda(self):
        respuesta = self._ajax(document_number='1020304050')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self._refrescar().document_number, '')

    def test_se_puede_borrar_el_documento(self):
        get_user_model().objects.filter(pk=self.usuario.pk).update(
            document_type='CC', document_number='1020304050',
        )
        self._post(document_type='', document_number='')
        usuario = self._refrescar()
        self.assertEqual((usuario.document_type, usuario.document_number), ('', ''))

    def test_un_envio_sin_campos_de_documento_no_lo_borra(self):
        get_user_model().objects.filter(pk=self.usuario.pk).update(
            document_type='CC', document_number='1020304050',
        )
        self._post(first_name='Nueva')
        self.assertEqual(self._refrescar().document_number, '1020304050')

    def test_el_formulario_muestra_el_documento_guardado(self):
        get_user_model().objects.filter(pk=self.usuario.pk).update(
            document_type='CE', document_number='998877',
        )
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="998877"')
        self.assertContains(respuesta, '<option value="CE" selected>')

    def test_sin_cambios_lo_informa(self):
        respuesta = self._ajax(first_name='Ana', last_name='Marin', age='30')
        self.assertEqual(respuesta.json(), {'ok': True, 'message': 'No se realizaron cambios.'})

    def test_cambio_ajax_confirma(self):
        respuesta = self._ajax(first_name='Nueva')
        self.assertEqual(respuesta.json()['message'], 'Perfil actualizado correctamente.')

    def test_edad_invalida(self):
        respuesta = self._ajax(age='abc')
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['ok'])
        self.assertRedirects(self._post(age='abc'), self.url, fetch_redirect_response=False)

    def test_correo_en_uso_por_otra_cuenta(self):
        _usuario('ocupado@example.com')
        respuesta = self._ajax(email='ocupado@example.com')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self._refrescar().email, 'cuenta@example.com')
        self.assertRedirects(self._post(email='ocupado@example.com'), self.url, fetch_redirect_response=False)

    def test_cambia_el_correo(self):
        self._post(email='nuevo@example.com')
        self.assertEqual(self._refrescar().email, 'nuevo@example.com')

    def test_cambio_de_contrasena_exitoso_mantiene_la_sesion(self):
        respuesta = self._ajax(current_password=CLAVE, password='Otra-Clave-456', password2='Otra-Clave-456')
        self.assertTrue(respuesta.json()['ok'])
        self.assertTrue(self._refrescar().check_password('Otra-Clave-456'))
        self.assertEqual(self.client.get(self.url).status_code, 200)  # sigue con sesion

    def test_rechaza_una_contrasena_que_no_cumple_las_reglas(self):
        respuesta = self._ajax(current_password=CLAVE, password='sencilla1', password2='sencilla1')
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['ok'])
        self.assertIn('mayúscula', respuesta.json()['message'])
        self.assertTrue(self._refrescar().check_password(CLAVE))

    def test_contrasenas_que_no_coinciden(self):
        respuesta = self._ajax(current_password=CLAVE, password='uno', password2='dos')
        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(self._refrescar().check_password(CLAVE))
        self.assertRedirects(
            self._post(current_password=CLAVE, password='uno', password2='dos'),
            self.url, fetch_redirect_response=False,
        )

    def test_contrasena_actual_incorrecta(self):
        respuesta = self._ajax(current_password='mala', password='nueva-123', password2='nueva-123')
        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(self._refrescar().check_password(CLAVE))
        self.assertRedirects(
            self._post(current_password='mala', password='nueva-123', password2='nueva-123'),
            self.url, fetch_redirect_response=False,
        )


class LibretaDeDireccionesRamasTests(TestCase):
    def setUp(self):
        self.usuario = _usuario()
        self.client.force_login(self.usuario)

    def test_la_libreta_redirige_al_perfil(self):
        self.assertRedirects(self.client.get(reverse('address_book')), reverse('edit_profile'))

    def test_formulario_de_direccion_nueva(self):
        self.assertEqual(self.client.get(reverse('address_new')).status_code, 200)

    def test_una_direccion_invalida_vuelve_al_formulario(self):
        respuesta = self.client.post(reverse('address_new'), {'country': 'Colombia'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['form'].errors)

    def test_get_a_eliminar_o_marcar_predeterminada_no_cambia_nada(self):
        from accounts.models import CustomerAddress
        direccion = CustomerAddress.objects.create(
            user=self.usuario, label='Casa', full_name='Ana', phone='1', country='Colombia',
            department='Bogotá D.C.', city='Bogotá', address_line='Calle 1',
        )
        self.client.get(reverse('address_delete', args=[direccion.pk]))
        self.client.get(reverse('address_set_default', args=[direccion.pk]))
        direccion.refresh_from_db()
        self.assertFalse(direccion.is_default)
