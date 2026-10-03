"""Recuperacion de contrasena de punta a punta.

El enlace "¿Olvidaste tu contrasena?" llevaba a una pagina que fallaba con
error 500: las plantillas cargaban `widget_tweaks`, que estaba en
requirements.txt pero no en INSTALLED_APPS. Estas pruebas recorren el flujo
completo para que no vuelva a pasar sin que nadie lo note.
"""
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse


class RecuperarContrasenaTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            email='olvido@example.com', username='olvido@example.com', password='clave-vieja-123',
        )

    def test_la_pantalla_para_pedir_el_enlace_se_muestra(self):
        respuesta = self.client.get(reverse('password_reset'))
        self.assertEqual(respuesta.status_code, 200)

    def test_el_enlace_del_login_lleva_a_una_pagina_que_funciona(self):
        login = self.client.get(reverse('commercial_login')).content.decode()
        destino = re.search(r'class="commercial-auth__forgot" href="([^"]+)"', login).group(1)
        self.assertEqual(self.client.get(destino).status_code, 200)

    def test_flujo_completo_hasta_entrar_con_la_contrasena_nueva(self):
        respuesta = self.client.post(reverse('password_reset'), {'email': 'olvido@example.com'})
        self.assertRedirects(respuesta, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['olvido@example.com'])

        enlace = re.search(r'https?://[^\s]+/accounts/reset/[^\s]+', mail.outbox[0].body).group(0)
        ruta = enlace.split('testserver', 1)[-1]
        formulario = self.client.get(ruta, follow=True)
        self.assertEqual(formulario.status_code, 200)

        enviado = self.client.post(
            formulario.redirect_chain[-1][0], {'new_password1': 'clave-nueva-456', 'new_password2': 'clave-nueva-456'},
        )
        self.assertRedirects(enviado, reverse('password_reset_complete'))
        self.assertEqual(self.client.get(reverse('password_reset_complete')).status_code, 200)

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('clave-nueva-456'))
        self.assertFalse(self.usuario.check_password('clave-vieja-123'))

    def test_un_correo_desconocido_no_revela_si_existe_la_cuenta(self):
        respuesta = self.client.post(reverse('password_reset'), {'email': 'nadie@example.com'})
        self.assertRedirects(respuesta, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_un_enlace_invalido_se_rechaza_sin_romper(self):
        respuesta = self.client.get(reverse('password_reset_confirm', args=['abc', 'token-falso']))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, reverse('password_reset'))  # ofrece pedir otro enlace
        self.assertNotContains(respuesta, 'new_password1')
