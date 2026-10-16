"""El administrador de Django solo admite superusuarios y limita los intentos de acceso."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


class AdministradorRestringidoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superusuario = User.objects.create_superuser(
            email='super@example.com', username='super@example.com', password='Clave-Segura-123',
        )
        self.personal = User.objects.create_user(
            email='personal@example.com', username='personal@example.com', password='Clave-Segura-123', is_staff=True,
        )
        self.url = reverse('admin:index')

    def test_el_superusuario_entra(self):
        self.client.force_login(self.superusuario)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_el_personal_sin_ser_superusuario_no_entra(self):
        self.client.force_login(self.personal)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])

    def test_el_visitante_va_al_acceso(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_el_formulario_de_acceso_limita_los_intentos(self):
        cache.clear()
        acceso = reverse('admin:login')
        codigos = [
            self.client.post(acceso, {'username': 'super@example.com', 'password': 'mala'}).status_code
            for _ in range(12)
        ]
        self.assertEqual(codigos[:10], [200] * 10)
        self.assertEqual(codigos[10:], [429, 429])
        cache.clear()

    def test_la_ruta_por_defecto_es_admin(self):
        # ADMIN_URL se lee al arrancar (ver settings.py); aqui se comprueba el valor por defecto.
        self.assertTrue(self.url.endswith('/admin/'))
