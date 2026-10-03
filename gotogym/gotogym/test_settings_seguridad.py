"""Configuracion segura de produccion.

La configuracion se evalua al importarla, asi que cada caso se ejecuta en un
proceso aparte con un entorno controlado: es la unica forma de probar lo que
pasa "al arrancar".
"""
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[1]
CLAVE = 'una-clave-larga-para-las-pruebas-' + 'x' * 40

LEER = """
import django
from django.conf import settings as s
print(
    s.PRODUCCION, s.SECURE_SSL_REDIRECT, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE,
    bool(getattr(s, 'SECURE_PROXY_SSL_HEADER', None)), s.SECURE_HSTS_SECONDS,
    s.CACHES['default']['BACKEND'].rsplit('.', 1)[-1], s.TASK_BACKEND,
)
"""


def _cargar(modulo='gotogym.settings', **entorno):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DJANGO_', 'SECURE_', 'DEBUG', 'REDIS', 'TASK_', 'SESSION_', 'CSRF_'))}
    env.update(DJANGO_SETTINGS_MODULE=modulo, PYTHONUTF8='1', **entorno)
    return subprocess.run(
        [sys.executable, '-c', LEER], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=60,
    )


class ClaveSecretaTests(SimpleTestCase):
    def test_produccion_sin_clave_no_arranca(self):
        resultado = _cargar()
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', resultado.stderr)

    def test_produccion_con_clave_arranca(self):
        self.assertEqual(_cargar(DJANGO_SECRET_KEY=CLAVE).returncode, 0)

    def test_desarrollo_y_pruebas_no_la_exigen(self):
        self.assertEqual(_cargar('gotogym.settings_local').returncode, 0)
        self.assertEqual(_cargar('gotogym.settings_test').returncode, 0)
        self.assertEqual(_cargar(DEBUG='true').returncode, 0)


class HttpsPorDefectoTests(SimpleTestCase):
    def test_en_produccion_todo_esta_activo_por_defecto_salvo_hsts(self):
        salida = _cargar(DJANGO_SECRET_KEY=CLAVE).stdout.strip().splitlines()[-1].split()
        self.assertEqual(salida[:6], ['True', 'True', 'True', 'True', 'True', '0'])

    def test_se_puede_apagar_expresamente(self):
        salida = _cargar(
            DJANGO_SECRET_KEY=CLAVE, SECURE_SSL_REDIRECT='false', SESSION_COOKIE_SECURE='false',
        ).stdout.strip().splitlines()[-1].split()
        self.assertEqual(salida[1:4], ['False', 'False', 'True'])

    def test_en_desarrollo_esta_apagado(self):
        salida = _cargar('gotogym.settings_local').stdout.strip().splitlines()[-1].split()
        self.assertEqual(salida[:5], ['False', 'False', 'False', 'False', 'False'])

    def test_hsts_solo_se_activa_por_variable(self):
        salida = _cargar(DJANGO_SECRET_KEY=CLAVE, SECURE_HSTS_SECONDS='3600').stdout.strip().splitlines()[-1].split()
        self.assertEqual(salida[5], '3600')


class CacheYTareasTests(SimpleTestCase):
    def test_sin_redis_usa_memoria_local_y_tareas_sincronas(self):
        salida = _cargar('gotogym.settings_test').stdout.strip().splitlines()[-1].split()
        self.assertEqual(salida[6:], ['LocMemCache', 'sync'])

    def test_con_redis_la_cache_es_compartida(self):
        salida = _cargar('gotogym.settings_test', REDIS_URL='redis://localhost:6379/1').stdout.strip().splitlines()[-1].split()
        self.assertEqual(salida[6], 'RedisCache')

    def test_el_backend_de_tareas_se_elige_por_variable(self):
        salida = _cargar('gotogym.settings_test', TASK_BACKEND='mi.Cola').stdout.strip().splitlines()[-1].split()
        self.assertEqual(salida[7], 'mi.Cola')
