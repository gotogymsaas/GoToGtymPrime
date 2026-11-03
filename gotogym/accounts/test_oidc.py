"""Entrar con la cuenta GoToGym (OIDC) en la tienda.

La logica del protocolo (state, nonce, PKCE, firma del token...) se prueba en
el paquete `gotogym_oidc`; aqui solo lo que es propio de la tienda: el boton,
la aceptacion de terminos de quien llega por primera vez, que el carrito no se
pierda y que cerrar sesion cierre tambien la del proveedor."""
import time
from unittest import mock
from urllib.parse import parse_qs, urlparse

import jwt
from carrito.services import SESSION_CART_KEY
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from gotogym_oidc.models import ExternalIdentityLink

ISSUER = 'https://idp.example/tenant/v2.0'
CLIENT_ID = 'tienda'
METADATA = {
    'issuer': ISSUER,
    'authorization_endpoint': 'https://idp.example/authorize',
    'token_endpoint': 'https://idp.example/token',
    'jwks_uri': 'https://idp.example/keys',
    'end_session_endpoint': 'https://idp.example/logout',
}
CONFIG = {
    'ENABLED': True, 'ISSUER': ISSUER, 'CLIENT_ID': CLIENT_ID, 'CLIENT_SECRET': 'x',
    'REDIRECT_URI': 'https://shop.example/accounts/oidc/callback/',
    'SUBJECT_CLAIM': 'oid', 'ADAPTER': 'accounts.oidc.PrimeAdapter',
    # Las pruebas de la tienda parten de un entorno donde el alta nueva esta
    # permitida; el valor por defecto del despliegue es cerrado.
    'ALLOW_AUTO_CREATE': True,
}
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
User = get_user_model()


def token(nonce, **extra):
    now = int(time.time())
    claims = {'iss': ISSUER, 'aud': CLIENT_ID, 'iat': now, 'exp': now + 300, 'nonce': nonce,
              'sub': 'sub-de-la-tienda', 'oid': 'oid-777', 'email': 'laura@example.com',
              'given_name': 'Laura', 'family_name': 'Pérez', 'email_verified': True}
    claims.update(extra)
    return jwt.encode(claims, KEY, algorithm='RS256', headers={'kid': 'k'})


@override_settings(GOTOGYM_OIDC=CONFIG, OIDC_HABILITADO=True, OIDC_GLOBAL=True)
class EntrarConGoToGymTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        for p in (
            mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA),
            mock.patch('gotogym_oidc.client.get_signing_key', side_effect=lambda t, u: KEY.public_key()),
        ):
            p.start()
            self.addCleanup(p.stop)

    def entrar(self, next_url=None, **claims):
        inicio = reverse('gotogym_oidc:start') + (f'?next={next_url}' if next_url else '')
        respuesta = self.client.get(inicio)
        params = {k: v[0] for k, v in parse_qs(urlparse(respuesta['Location']).query).items()}
        resp_token = mock.Mock(status_code=200)
        resp_token.json.return_value = {'id_token': token(params['nonce'], **claims)}
        with mock.patch('gotogym_oidc.client.requests.post', return_value=resp_token):
            return self.client.get(reverse('gotogym_oidc:callback'), {'code': 'c', 'state': params['state']})

    # -- boton ------------------------------------------------------------
    def test_el_boton_aparece_en_acceso_y_registro_con_el_next(self):
        for nombre in ('commercial_login', 'register'):
            html = self.client.get(reverse(nombre) + '?next=/checkout/').content.decode()
            self.assertIn('Continuar con GoToGym', html, nombre)
            self.assertIn(reverse('gotogym_oidc:start') + '?next=/checkout/', html, nombre)

    @override_settings(OIDC_HABILITADO=False)
    def test_sin_configurar_no_hay_boton(self):
        for nombre in ('commercial_login', 'register'):
            self.assertNotIn('Continuar con GoToGym', self.client.get(reverse(nombre)).content.decode(), nombre)

    def test_existing_account_link_page_explains_preservation(self):
        User.objects.create_user(email='laura@example.com', username='laura', password='Local-Only-Test-123!')
        response = self.entrar()
        self.assertEqual(response.status_code, 302)
        page = self.client.get(reverse('gotogym_oidc:link'))
        self.assertContains(page, 'Continúa con tu cuenta de siempre')
        self.assertContains(page, 'Contraseña actual de GoToGym')
        self.assertContains(page, 'Solo debes vincular esta cuenta una vez por aplicación')
        self.assertContains(page, 'csrfmiddlewaretoken')
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(ExternalIdentityLink.objects.exists())

    # -- primera vez ------------------------------------------------------
    def test_primera_vez_crea_cuenta_y_pide_terminos_antes_de_seguir(self):
        respuesta = self.entrar(next_url='/pedidos/checkout/')
        usuario = User.objects.get(email='laura@example.com')
        self.assertFalse(usuario.accepted_terms)
        self.assertEqual(ExternalIdentityLink.objects.get().subject, 'oid-777')
        self.assertEqual(int(self.client.session['_auth_user_id']), usuario.pk)
        destino = urlparse(respuesta['Location'])
        self.assertEqual(destino.path, reverse('accept_terms'))
        self.assertEqual(parse_qs(destino.query)['next'], ['/pedidos/checkout/'])

    def test_aceptar_terminos_registra_la_aceptacion_y_sigue(self):
        self.entrar(next_url='/pedidos/checkout/')
        sin_marcar = self.client.post(reverse('accept_terms'), {'next': '/pedidos/checkout/'})
        self.assertEqual(sin_marcar.status_code, 200)
        self.assertFalse(User.objects.get().accepted_terms)
        marcado = self.client.post(reverse('accept_terms'), {'next': '/pedidos/checkout/', 'accepted_terms': 'on'})
        self.assertRedirects(marcado, '/pedidos/checkout/', fetch_redirect_response=False)
        usuario = User.objects.get()
        self.assertTrue(usuario.accepted_terms)
        self.assertIsNotNone(usuario.terms_accepted_at)
        self.assertEqual(len(usuario.terms_hash), 128)

    def test_aceptar_terminos_no_redirige_a_otro_sitio(self):
        self.entrar()
        respuesta = self.client.post(reverse('accept_terms'), {'next': 'https://evil.example/', 'accepted_terms': 'on'})
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)

    def test_aceptar_terminos_exige_sesion(self):
        respuesta = self.client.get(reverse('accept_terms'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('commercial_login'), respuesta['Location'])

    def test_el_carrito_del_invitado_sobrevive_al_entrar(self):
        sesion = self.client.session
        sesion[SESSION_CART_KEY] = {'1': 2}
        sesion.save()
        self.entrar()
        self.assertEqual(self.client.session[SESSION_CART_KEY], {'1': 2})

    def test_terms_cannot_be_bypassed_by_direct_navigation(self):
        self.entrar()
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(reverse('accept_terms')))

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)

    # -- cuenta de la tienda que ya existia --------------------------------
    def test_cuenta_existente_con_mismo_correo_pide_su_clave_y_no_pide_terminos(self):
        existente = User.objects.create_user(
            email='laura@example.com', username='laura', password='Clave-Segura-123', accepted_terms=True,
        )
        respuesta = self.entrar(next_url='/pedidos/checkout/')
        self.assertRedirects(respuesta, reverse('gotogym_oidc:link'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        final = self.client.post(reverse('gotogym_oidc:link'), {'password': 'Clave-Segura-123'})
        self.assertRedirects(final, '/pedidos/checkout/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), existente.pk)
        self.assertEqual(User.objects.count(), 1)

    # -- salir -------------------------------------------------------------
    def test_cerrar_sesion_tras_entrar_con_goToGym_cierra_tambien_la_del_proveedor(self):
        self.entrar()
        respuesta = self.client.post(reverse('logout'))
        self.assertTrue(respuesta['Location'].startswith(METADATA['end_session_endpoint']))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_cerrar_sesion_de_quien_entro_con_clave_no_toca_al_proveedor(self):
        User.objects.create_user(email='a@example.com', username='a', password='Clave-Segura-123')
        self.client.post(reverse('commercial_login'), {'username': 'a@example.com', 'password': 'Clave-Segura-123'})
        respuesta = self.client.post(reverse('logout'))
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)


@override_settings(GOTOGYM_OIDC=CONFIG, OIDC_HABILITADO=True, OIDC_GLOBAL=True, OIDC_SOLO_GOTOGYM=True)
class IrDirectoAGoToGymTests(TestCase):
    """Con OIDC_SOLO_GOTOGYM no hay pantalla intermedia con el boton."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_iniciar_sesion_y_crear_cuenta_van_directo_al_proveedor(self):
        for nombre in ('commercial_login', 'login', 'register'):
            respuesta = self.client.get(reverse(nombre))
            self.assertRedirects(respuesta, reverse('gotogym_oidc:start'), fetch_redirect_response=False)

    def test_conserva_el_destino_seguro_y_descarta_el_ajeno(self):
        respuesta = self.client.get(reverse('commercial_login'), {'next': '/pedidos/checkout/'})
        self.assertRedirects(
            respuesta, reverse('gotogym_oidc:start') + '?next=%2Fpedidos%2Fcheckout%2F', fetch_redirect_response=False,
        )
        ajeno = self.client.get(reverse('commercial_login'), {'next': 'https://evil.example/'})
        self.assertRedirects(ajeno, reverse('gotogym_oidc:start'), fetch_redirect_response=False)

    def test_el_acceso_propio_sigue_disponible_con_legacy(self):
        respuesta = self.client.get(reverse('commercial_login'), {'legacy': '1'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'name="password"')

    def test_el_formulario_propio_sigue_funcionando_por_post(self):
        User.objects.create_user(email='a@example.com', username='a', password='Clave-Segura-123')
        respuesta = self.client.post(
            reverse('commercial_login') + '?legacy=1',
            {'username': 'a@example.com', 'password': 'Clave-Segura-123'},
        )
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)

    def test_quien_ya_tiene_sesion_no_es_redirigido(self):
        User.objects.create_user(email='a@example.com', username='a', password='Clave-Segura-123')
        self.client.login(username='a@example.com', password='Clave-Segura-123')
        self.assertEqual(self.client.get(reverse('commercial_login')).status_code, 200)

    def test_un_fallo_del_proveedor_no_crea_un_bucle(self):
        # Callback sin flujo previo: falla; debe terminar en el formulario propio.
        respuesta = self.client.get(reverse('gotogym_oidc:callback'), {'code': 'x', 'state': 'y'}, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertLessEqual(len(respuesta.redirect_chain), 2)
        self.assertContains(respuesta, 'name="password"')

    @override_settings(OIDC_HABILITADO=False)
    def test_sin_oidc_configurado_no_redirige_aunque_este_activado(self):
        self.assertEqual(self.client.get(reverse('commercial_login')).status_code, 200)

    @override_settings(OIDC_SOLO_GOTOGYM=False)
    def test_apagado_conserva_la_pantalla_con_el_boton(self):
        respuesta = self.client.get(reverse('commercial_login'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Continuar con GoToGym')
