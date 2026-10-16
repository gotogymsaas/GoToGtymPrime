"""Intentos repetidos de acceso, registro y recuperacion de contrasena."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(RATE_LIMIT_ENABLED=True)
class LimitesDeAccesoTests(TestCase):
    def setUp(self):
        cache.clear()
        get_user_model().objects.create_user(
            email='limite@example.com', username='limite@example.com', password='Clave-Segura-123',
        )

    def tearDown(self):
        cache.clear()

    def test_el_login_se_bloquea_tras_diez_intentos_fallidos(self):
        url = reverse('commercial_login')
        codigos = [
            self.client.post(url, {'username': 'limite@example.com', 'password': 'mala'}).status_code
            for _ in range(12)
        ]
        self.assertEqual(codigos[:10], [200] * 10)
        self.assertEqual(codigos[10:], [429, 429])

    def test_ver_el_formulario_no_cuenta(self):
        url = reverse('commercial_login')
        self.assertTrue(all(self.client.get(url).status_code == 200 for _ in range(15)))

    def test_el_registro_se_limita_por_hora(self):
        url = reverse('register')
        codigos = [self.client.post(url, {'first_name': 'A'}).status_code for _ in range(12)]
        self.assertEqual(codigos[10:], [429, 429])

    def test_la_recuperacion_de_contrasena_se_limita(self):
        url = reverse('password_reset')
        codigos = [self.client.post(url, {'email': 'limite@example.com'}).status_code for _ in range(7)]
        self.assertEqual(codigos[:5], [302] * 5)
        self.assertEqual(codigos[5:], [429, 429])
