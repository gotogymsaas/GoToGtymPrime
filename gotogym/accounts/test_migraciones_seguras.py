"""Las migraciones no deben crear cuentas con credenciales conocidas ni llevar
datos personales dentro del codigo."""
import importlib
import re
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

MIGRACIONES = Path(__file__).resolve().parent / 'migrations'


def _cargar(nombre):
    return importlib.import_module(f'accounts.migrations.{nombre}')


class AdministradorInicialTests(TestCase):
    def setUp(self):
        get_user_model().objects.all().delete()

    def test_sin_variable_no_se_crea_ningun_administrador(self):
        with patch.dict('os.environ', {}, clear=False) as entorno:
            entorno.pop('GOTOGYM_ADMIN_PASSWORD', None)
            _cargar('0005_bootstrap_admin_user').bootstrap_admin(apps, None)
            _cargar('0006_ensure_admin_user').ensure_admin(apps, None)
        self.assertFalse(get_user_model().objects.exists())

    def test_con_variable_se_crea_con_esa_contrasena(self):
        with patch.dict('os.environ', {
            'GOTOGYM_ADMIN_PASSWORD': 'una-clave-del-entorno-123', 'GOTOGYM_ADMIN_EMAIL': 'dueno@example.com',
        }):
            _cargar('0005_bootstrap_admin_user').bootstrap_admin(apps, None)
        admin = get_user_model().objects.get(email='dueno@example.com')
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password('una-clave-del-entorno-123'))

    def test_una_base_nueva_de_pruebas_no_trae_cuentas_heredadas(self):
        # El setUp vacia la tabla; esto comprueba ademas que las migraciones
        # ya no restauran personas reales.
        self.assertEqual(_cargar('0007_restore_local_users').USERS, [])


class CodigoLimpioTests(TestCase):
    def test_ninguna_migracion_lleva_una_contrasena_por_defecto(self):
        for archivo in MIGRACIONES.glob('*.py'):
            texto = archivo.read_text(encoding='utf-8')
            self.assertNotIn('EricViana@2026', texto, archivo.name)
            self.assertIsNone(re.search(r'os\.environ\.get\("GOTOGYM_ADMIN_PASSWORD",\s*"[^"]+"', texto), archivo.name)

    # 0009 no crea cuentas ni guarda contrasenas: solo promueve a personal una
    # cuenta que YA existe. Es una decision de permisos, no un dato personal
    # insertado, y por eso queda fuera de esta comprobacion.
    EXCEPCIONES = {'0009_sincroniza_roles_de_usuario.py'}

    def test_ninguna_migracion_lleva_hashes_de_contrasena_ni_correos_reales(self):
        for archivo in MIGRACIONES.glob('*.py'):
            if archivo.name in self.EXCEPCIONES:
                continue
            texto = archivo.read_text(encoding='utf-8')
            self.assertNotIn('pbkdf2_sha256$', texto, archivo.name)
            for correo in set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', texto)):
                self.assertTrue(
                    correo.endswith(('@gotogym.com', '@gotogym.store', '@example.com')),
                    f'{archivo.name}: {correo}',
                )
