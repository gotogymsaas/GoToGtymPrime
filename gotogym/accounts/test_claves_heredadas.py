from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management import call_command
from django.test import TestCase

from accounts.management.commands.revisar_claves_heredadas import (
    CLAVES_PUBLICADAS,
    clave_aleatoria,
)


class RevisarClavesHeredadasTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.expuesta = User.objects.create_superuser(
            email='admin@gotogym.com', username='ericviana', password=CLAVES_PUBLICADAS[0],
        )
        self.sana = User.objects.create_user(
            email='cliente@example.com', username='cliente@example.com', password='Clave-Segura-123',
        )

    def _ejecutar(self, *args):
        salida = StringIO()
        call_command('revisar_claves_heredadas', *args, stdout=salida)
        return salida.getvalue()

    def test_informa_la_cuenta_expuesta_sin_cambiarla(self):
        texto = self._ejecutar()
        self.assertIn('AFECTADA: admin@gotogym.com (superusuario)', texto)
        self.assertNotIn('cliente@example.com', texto)
        self.expuesta.refresh_from_db()
        self.assertTrue(self.expuesta.check_password(CLAVES_PUBLICADAS[0]))

    def test_rotar_cambia_la_clave_y_la_muestra_una_vez(self):
        texto = self._ejecutar('--rotar')
        self.expuesta.refresh_from_db()
        self.assertFalse(self.expuesta.check_password(CLAVES_PUBLICADAS[0]))
        nueva = texto.split('no se vuelve a mostrar): ')[1].splitlines()[0]
        self.assertTrue(self.expuesta.check_password(nueva))
        self.assertIn('Ninguna cuenta', self._ejecutar())

    def test_no_toca_las_cuentas_sanas(self):
        self._ejecutar('--rotar')
        self.sana.refresh_from_db()
        self.assertTrue(self.sana.check_password('Clave-Segura-123'))

    def test_la_clave_generada_cumple_las_reglas_de_la_tienda(self):
        for _ in range(20):
            validate_password(clave_aleatoria())
