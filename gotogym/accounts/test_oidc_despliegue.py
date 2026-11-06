"""Puesta en marcha segura del inicio de sesion unificado en la tienda.

`test_oidc.py` prueba la experiencia del cliente con el acceso abierto a todos.
Aqui se prueba lo que protege el despliegue: el canary, los valores que fallan
cerrados, que las cuentas existentes no cambien al vincularse, que un token mal
formado no abra sesion y el diagnostico `oidc_preflight`.

El protocolo (firma, `aud`, `iss`, `exp`, PKCE) se prueba a fondo en el paquete
`gotogym_oidc`; aqui se comprueba que cada rechazo llega a la tienda sin crear
sesion, cuenta ni vinculo."""
import json
from io import StringIO
from unittest import mock
from urllib.parse import parse_qs, urlparse

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from gotogym_oidc.models import ExternalIdentityLink

from accounts.test_oidc import CONFIG, KEY, METADATA, token

User = get_user_model()
CLAVE = 'Clave-Segura-123'


class ProveedorSimulado(TestCase):
    """Base: proveedor simulado y un `entrar` que permite romper el token."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        for p in (
            mock.patch('gotogym_oidc.client.get_metadata', return_value=METADATA),
            mock.patch('gotogym_oidc.client.get_signing_key', side_effect=lambda t, u: KEY.public_key()),
        ):
            p.start()
            self.addCleanup(p.stop)

    def entrar(self, state=None, **claims):
        respuesta = self.client.get(reverse('gotogym_oidc:start'))
        params = {k: v[0] for k, v in parse_qs(urlparse(respuesta['Location']).query).items()}
        del_token = mock.Mock(status_code=200)
        del_token.json.return_value = {'id_token': token(params['nonce'], **claims)}
        with mock.patch('gotogym_oidc.client.requests.post', return_value=del_token):
            return self.client.get(
                reverse('gotogym_oidc:callback'), {'code': 'c', 'state': state or params['state']},
            )

    def assert_sin_sesion_ni_cuenta(self, cuentas_antes=0):
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(User.objects.count(), cuentas_antes)
        self.assertEqual(ExternalIdentityLink.objects.count(), 0)


@override_settings(
    GOTOGYM_OIDC=CONFIG, OIDC_HABILITADO=True, OIDC_GLOBAL=False, OIDC_CANARY=True,
    OIDC_CANARY_OBJECT_IDS=frozenset({'oid-777'}),
)
class CanaryTests(ProveedorSimulado):
    def test_el_boton_esta_oculto_salvo_para_quien_prueba(self):
        self.assertNotContains(self.client.get(reverse('commercial_login')), 'Continuar con GoToGym')
        self.assertContains(self.client.get(reverse('commercial_login') + '?sso=1'), 'Continuar con GoToGym')

    def test_entra_quien_esta_en_la_lista(self):
        self.entrar()
        self.assertIn('_auth_user_id', self.client.session)

    def test_quien_no_esta_en_la_lista_no_abre_sesion_ni_crea_cuenta(self):
        respuesta = self.entrar(oid='oid-ajeno')
        self.assertIn('oidc_error', respuesta['Location'])
        self.assert_sin_sesion_ni_cuenta()

    def test_una_identidad_vinculada_fuera_de_la_lista_tampoco_entra(self):
        usuario = User.objects.create_user(email='otra@example.com', username='otra', password=CLAVE)
        ExternalIdentityLink.objects.create(user=usuario, issuer=METADATA['issuer'], subject='oid-ajeno')
        self.entrar(oid='oid-ajeno', email='otra@example.com')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_el_login_con_clave_sigue_funcionando(self):
        User.objects.create_user(email='a@example.com', username='a', password=CLAVE)
        respuesta = self.client.post(reverse('commercial_login'), {'username': 'a@example.com', 'password': CLAVE})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)


@override_settings(GOTOGYM_OIDC=CONFIG, OIDC_HABILITADO=True, OIDC_GLOBAL=True)
class RechazosTests(ProveedorSimulado):
    """Cada fallo del proveedor vuelve a la pantalla propia y no deja rastro."""

    def assert_rechazado(self, respuesta):
        self.assertIn('oidc_error', respuesta['Location'])
        self.assert_sin_sesion_ni_cuenta()

    def test_token_vencido(self):
        self.assert_rechazado(self.entrar(exp=1))

    def test_emisor_incorrecto(self):
        self.assert_rechazado(self.entrar(iss='https://otro-emisor.example/v2.0'))

    def test_audiencia_incorrecta(self):
        self.assert_rechazado(self.entrar(aud='otra-aplicacion'))

    def test_state_invalido(self):
        self.assert_rechazado(self.entrar(state='falsificado'))

    def test_correo_sin_verificar(self):
        self.assert_rechazado(self.entrar(email_verified=False))

    def test_sin_el_claim_de_correo_verificado_se_rechaza_por_defecto(self):
        self.assert_rechazado(self.entrar(email_verified=None))

    def test_proveedor_caido(self):
        inicio = self.client.get(reverse('gotogym_oidc:start'))
        state = parse_qs(urlparse(inicio['Location']).query)['state'][0]
        with mock.patch('gotogym_oidc.client.get_metadata', side_effect=requests.ConnectionError('sin red')):
            respuesta = self.client.get(reverse('gotogym_oidc:callback'), {'code': 'c', 'state': state})
        self.assertIn('oidc_error', respuesta['Location'])
        self.assertNotIn('_auth_user_id', self.client.session)
        # La pantalla propia sigue disponible.
        self.assertEqual(self.client.get(reverse('commercial_login') + '?legacy=1').status_code, 200)

    @override_settings(GOTOGYM_OIDC={**CONFIG, 'ALLOW_AUTO_CREATE': False})
    def test_sin_alta_nueva_no_se_crea_la_cuenta(self):
        self.assert_rechazado(self.entrar())


@override_settings(GOTOGYM_OIDC=CONFIG, OIDC_HABILITADO=True, OIDC_GLOBAL=True)
class CuentasExistentesTests(ProveedorSimulado):
    """Vincular una identidad no puede cambiar nada de la cuenta local."""

    def crear_cuenta(self):
        return User.objects.create_user(
            email='laura@example.com', username='laura', password=CLAVE, accepted_terms=True,
            is_staff=True, is_superuser=True, es_afiliado=True, phone='3000000000',
        )

    def campos(self, usuario):
        usuario.refresh_from_db()
        return {
            n: getattr(usuario, n)
            for n in ('pk', 'email', 'username', 'password', 'is_active', 'is_staff', 'is_superuser',
                      'es_afiliado', 'accepted_terms', 'terms_hash', 'phone')
        }

    def test_vincular_con_la_clave_correcta_no_cambia_ningun_campo_protegido(self):
        usuario = self.crear_cuenta()
        antes = self.campos(usuario)
        self.entrar()
        self.client.post(reverse('gotogym_oidc:link'), {'password': CLAVE})
        self.assertEqual(int(self.client.session['_auth_user_id']), usuario.pk)
        self.assertEqual(self.campos(usuario), antes)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(ExternalIdentityLink.objects.filter(user=usuario).count(), 1)

    def test_el_mismo_correo_sin_la_clave_no_vincula_ni_inicia_sesion(self):
        usuario = self.crear_cuenta()
        antes = self.campos(usuario)
        self.entrar()
        self.client.post(reverse('gotogym_oidc:link'), {'password': 'clave-equivocada'})
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(ExternalIdentityLink.objects.count(), 0)
        self.assertEqual(self.campos(usuario), antes)

    def test_la_clave_actual_sigue_sirviendo_despues_de_vincular(self):
        self.crear_cuenta()
        self.entrar()
        self.client.post(reverse('gotogym_oidc:link'), {'password': CLAVE})
        self.client.post(reverse('logout'))
        respuesta = self.client.post(reverse('commercial_login'), {'username': 'laura@example.com', 'password': CLAVE})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_dos_personas_con_la_misma_identidad_no_se_mezclan(self):
        primera = User.objects.create_user(email='a@example.com', username='a', password=CLAVE)
        ExternalIdentityLink.objects.create(user=primera, issuer=METADATA['issuer'], subject='oid-777')
        self.entrar(email='laura@example.com')
        self.assertEqual(int(self.client.session['_auth_user_id']), primera.pk)


class ValoresPorDefectoTests(TestCase):
    """Lo que ya no depende del valor por defecto del modulo compartido."""

    def test_los_controles_clave_fallan_cerrados(self):
        self.assertIs(settings.GOTOGYM_OIDC['REQUIRE_CLIENT_SECRET'], True)
        self.assertIs(settings.GOTOGYM_OIDC['ALLOW_AUTO_CREATE'], False)
        self.assertIs(settings.GOTOGYM_OIDC['REQUIRE_EMAIL_VERIFIED_CLAIM'], True)

    def test_configurar_el_proveedor_no_lo_enciende(self):
        self.assertFalse(settings.OIDC_HABILITADO)
        self.assertFalse(settings.OIDC_GLOBAL)
        self.assertFalse(settings.OIDC_SOLO_GOTOGYM)


class PreflightTests(TestCase):
    def ejecutar(self, *args):
        salida = StringIO()
        call_command('oidc_preflight', *args, stdout=salida)
        return json.loads(salida.getvalue())

    def estado(self, informe):
        return {v['check']: v['ok'] for v in informe['checks']}

    def test_sin_configuracion_no_esta_listo(self):
        informe = self.ejecutar()
        self.assertFalse(informe['ready'])
        self.assertEqual(informe['mode'], 'apagado')

    @override_settings(GOTOGYM_OIDC={**CONFIG, 'CLIENT_SECRET': 'valor-secreto-123'})
    def test_no_imprime_el_secreto(self):
        salida = StringIO()
        call_command('oidc_preflight', '--discovery', '--audit-preservation', stdout=salida)
        self.assertNotIn('valor-secreto-123', salida.getvalue())

    @override_settings(GOTOGYM_OIDC={**CONFIG, 'CLIENT_SECRET': '@Microsoft.KeyVault(SecretUri=https://kv.example/secrets/x)'})
    def test_detecta_una_referencia_de_key_vault_sin_resolver(self):
        self.assertFalse(self.estado(self.ejecutar())['client_secret_resuelto'])

    @override_settings(GOTOGYM_OIDC=CONFIG, OIDC_CANARY=True, OIDC_CANARY_OBJECT_IDS=frozenset())
    def test_canary_sin_lista_es_bloqueante(self):
        self.assertFalse(self.estado(self.ejecutar())['canary_con_lista'])

    @override_settings(GOTOGYM_OIDC={**CONFIG, 'REDIRECT_URI': 'http://shop.example/accounts/oidc/callback/'})
    def test_exige_https_en_la_url_de_retorno(self):
        self.assertFalse(self.estado(self.ejecutar())['redirect_uri_valida'])

    @override_settings(GOTOGYM_OIDC=CONFIG)
    def test_configuracion_correcta_queda_lista(self):
        informe = self.ejecutar()
        self.assertTrue(informe['ready'], informe['checks'])

    def test_strict_falla_si_no_esta_listo(self):
        with self.assertRaises(CommandError):
            call_command('oidc_preflight', '--strict', stdout=StringIO())

    @override_settings(GOTOGYM_OIDC=CONFIG)
    def test_discovery_con_otro_issuer_es_bloqueante(self):
        with mock.patch('gotogym_oidc.client.get_metadata', return_value={**METADATA, 'issuer': 'https://otro.example/v2.0'}):
            self.assertFalse(self.estado(self.ejecutar('--discovery'))['issuer_coincide_con_el_discovery'])

    @override_settings(PRODUCCION=True, GOTOGYM_OIDC={
        **CONFIG,
        'ISSUER': 'https://fe3cd367-0570-48e7-8a35-a777b62cc6f9.ciamlogin.com/fe3cd367-0570-48e7-8a35-a777b62cc6f9/v2.0',
        'CLIENT_ID': 'cliente-prime-independiente',
        'REDIRECT_URI': 'https://shop.gotogym.store/accounts/oidc/callback/',
    })
    def test_configuracion_prime_produccion_separa_tenant_cliente_y_callback(self):
        checks = self.estado(self.ejecutar())
        self.assertTrue(checks['cliente_prime_independiente'])
        self.assertTrue(checks['tenant_externo_correcto'])
        self.assertTrue(checks['callback_prime_exacta'])

    @override_settings(PRODUCCION=True, GOTOGYM_OIDC={
        **CONFIG, 'CLIENT_ID': '4fd1c894-78fa-496e-aaf2-5361da0dc430',
        'REDIRECT_URI': 'https://shop.gotogym.store/accounts/oidc/callback/',
    })
    def test_reutilizar_cliente_coach_se_bloquea_en_produccion(self):
        checks = self.estado(self.ejecutar())
        self.assertFalse(checks['cliente_prime_independiente'])
        self.assertFalse(checks['tenant_externo_correcto'])

    @override_settings(PRODUCCION=True, GOTOGYM_OIDC={
        **CONFIG, 'CLIENT_ID': 'cliente-prime-independiente',
        'ISSUER': 'https://fe3cd367-0570-48e7-8a35-a777b62cc6f9.ciamlogin.com/fe3cd367-0570-48e7-8a35-a777b62cc6f9/v2.0',
        'REDIRECT_URI': 'https://other.example/accounts/oidc/callback/',
    })
    def test_callback_fuera_del_dominio_shop_se_bloquea_en_produccion(self):
        self.assertFalse(self.estado(self.ejecutar())['callback_prime_exacta'])

    def test_la_huella_no_cambia_si_nada_cambia_y_cambia_con_una_contrasena(self):
        usuario = User.objects.create_user(email='a@example.com', username='a', password=CLAVE, is_staff=True)
        primera = self.ejecutar('--audit-preservation')['preservation']
        segunda = self.ejecutar('--audit-preservation')['preservation']
        self.assertEqual(primera['keyed_fingerprint'], segunda['keyed_fingerprint'])
        self.assertEqual(primera['accounts'], 1)
        self.assertFalse(primera['writes_performed'])
        self.assertNotIn('a@example.com', json.dumps(primera))
        usuario.set_password('otra-clave-123')
        usuario.save()
        tercera = self.ejecutar('--audit-preservation')['preservation']
        self.assertNotEqual(primera['keyed_fingerprint'], tercera['keyed_fingerprint'])

    def test_ultimo_acceso_no_altera_la_huella(self):
        usuario = User.objects.create_user(email='a@example.com', username='a', password=CLAVE)
        antes = self.ejecutar('--audit-preservation')['preservation']['keyed_fingerprint']
        self.client.force_login(usuario)
        usuario.refresh_from_db()
        despues = self.ejecutar('--audit-preservation')['preservation']['keyed_fingerprint']
        self.assertEqual(antes, despues)
