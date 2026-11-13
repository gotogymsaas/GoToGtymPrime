"""Preferencia de linea de ropa en Mi cuenta."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PreferenciaDeLineaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            email='linea@example.com', username='linea', password='x', first_name='Ana', last_name='Ruiz',
        )
        self.client.force_login(self.usuario)

    def _guardar(self, **campos):
        datos = {'first_name': 'Ana', 'last_name': 'Ruiz', 'email': 'linea@example.com', 'phone': '', **campos}
        return self.client.post(reverse('edit_profile'), datos)

    def test_el_formulario_muestra_el_selector(self):
        respuesta = self.client.get(reverse('edit_profile'))
        self.assertContains(respuesta, 'name="clothing_line"')
        self.assertContains(respuesta, 'value="caballero"')

    def test_se_guarda_y_se_puede_quitar(self):
        self._guardar(clothing_line='caballero')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.clothing_line, 'caballero')

        self._guardar(clothing_line='')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.clothing_line, '')

    def test_un_valor_desconocido_no_se_guarda(self):
        self._guardar(clothing_line='otra')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.clothing_line, '')

    def test_un_envio_sin_el_campo_no_la_borra(self):
        self.usuario.clothing_line = 'dama'
        self.usuario.save()
        self._guardar()
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.clothing_line, 'dama')
