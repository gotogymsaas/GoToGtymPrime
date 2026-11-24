"""Base de datos y credenciales de integraciones, tal como las deja la
configuracion al arrancar.

La configuracion se evalua al importarla, asi que cada caso se ejecuta en un
proceso aparte con un entorno controlado (ver `test_settings_seguridad`).
"""
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[1]

LEER_CREDENCIALES = """
import django
django.setup()
from integrations.alegra.alegra_client import AlegraClient, AlegraConfigError
from integrations.mercadopago.mercadopago_client import MercadoPagoClient
try:
    alegra = AlegraClient()
    print('alegra', alegra.email, alegra.token)
except AlegraConfigError:
    print('alegra sin-credenciales')
try:
    print('mp', MercadoPagoClient().access_token)
except RuntimeError as error:
    print('mp', type(error).__name__)
"""


def _correr(codigo, **entorno):
    quitar = ('MYSQL_', 'DATABASE_URL', 'ALEGRA_', 'MERCADOPAGO_')
    env = {k: v for k, v in os.environ.items() if not k.startswith(quitar)}
    env.update(DJANGO_SETTINGS_MODULE='gotogym.settings_test', PYTHONUTF8='1', **entorno)
    return subprocess.run(
        [sys.executable, '-c', codigo], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120,
    )


class BaseDeDatosTests(SimpleTestCase):
    def test_declarar_mysql_falla_con_un_mensaje_claro(self):
        resultado = _correr('import django; django.setup()', MYSQL_HOST='db.example.com')
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('ImproperlyConfigured', resultado.stderr)
        self.assertIn('DATABASE_URL', resultado.stderr)

    def test_declarar_solo_la_base_de_mysql_tambien_falla(self):
        resultado = _correr('import django; django.setup()', MYSQL_DATABASE='gotogym_bd')
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('MySQL', resultado.stderr)

    def test_sin_variables_de_mysql_arranca(self):
        self.assertEqual(_correr('import django; django.setup()').returncode, 0)


class CredencialesDeIntegracionesTests(SimpleTestCase):
    def _leer(self, **entorno):
        resultado = _correr(LEER_CREDENCIALES, **entorno)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        return dict(linea.split(' ', 1) for linea in resultado.stdout.strip().splitlines()[-2:])

    def test_sin_variables_no_hay_credenciales(self):
        leido = self._leer()
        self.assertEqual(leido['alegra'], 'sin-credenciales')
        self.assertEqual(leido['mp'], 'RuntimeError')

    def test_alegra_lee_el_correo_y_el_token_del_entorno(self):
        leido = self._leer(ALEGRA_EMAIL='a@b.co', ALEGRA_API_TOKEN='nuevo')
        self.assertEqual(leido['alegra'], 'a@b.co nuevo')

    def test_alegra_cae_en_alegra_token_si_falta_el_otro(self):
        self.assertEqual(self._leer(ALEGRA_EMAIL='a@b.co', ALEGRA_TOKEN='viejo')['alegra'], 'a@b.co viejo')
        self.assertEqual(
            self._leer(ALEGRA_EMAIL='a@b.co', ALEGRA_API_TOKEN='', ALEGRA_TOKEN='viejo')['alegra'], 'a@b.co viejo',
        )

    def test_alegra_prefiere_alegra_api_token(self):
        leido = self._leer(ALEGRA_EMAIL='a@b.co', ALEGRA_API_TOKEN='nuevo', ALEGRA_TOKEN='viejo')
        self.assertEqual(leido['alegra'], 'a@b.co nuevo')

    def test_mercado_pago_lee_su_token_del_entorno(self):
        self.assertEqual(self._leer(MERCADOPAGO_ACCESS_TOKEN='del-entorno')['mp'], 'del-entorno')
