"""Reglas de contrasena: 8 caracteres o mas, con mayuscula, minuscula, numero
y un caracter especial; explicadas en el registro y aplicadas en el registro,
el perfil y el restablecimiento por correo."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

MINIMO = {'first_name': 'Ana', 'email': 'ana-reglas@example.com', 'accepted_terms': 'on'}


class ValidadorTests(TestCase):
    def test_acepta_una_contrasena_que_cumple_todo(self):
        validate_password('Clave-Segura-123')

    def test_rechaza_cada_regla_incumplida(self):
        casos = {
            'Ab1!': 'al menos 8 caracteres',
            'clave-segura-123': 'una mayúscula',
            'CLAVE-SEGURA-123': 'una minúscula',
            'Clave-Segura-abc': 'un número',
            'ClaveSegura123': 'un carácter especial',
        }
        for clave, esperado in casos.items():
            with self.subTest(clave=clave), self.assertRaises(ValidationError) as contexto:
                validate_password(clave)
            self.assertIn(esperado, ' '.join(contexto.exception.messages))

    def test_una_clave_vacia_lista_todo_lo_que_falta(self):
        with self.assertRaises(ValidationError) as contexto:
            validate_password('')
        mensaje = ' '.join(contexto.exception.messages)
        for parte in ('8 caracteres', 'mayúscula', 'minúscula', 'número', 'carácter especial'):
            self.assertIn(parte, mensaje)


class RegistroTests(TestCase):
    url = property(lambda self: reverse('register'))

    def test_el_formulario_explica_las_reglas(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Mínimo 8 caracteres')
        self.assertContains(respuesta, 'carácter especial')

    def test_rechaza_una_contrasena_debil_y_no_crea_la_cuenta(self):
        respuesta = self.client.post(self.url, {**MINIMO, 'password1': 'sencilla'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'La contraseña debe tener')
        self.assertFalse(get_user_model().objects.filter(email=MINIMO['email']).exists())

    def test_acepta_una_contrasena_que_cumple(self):
        self.client.post(self.url, {**MINIMO, 'password1': 'Clave-Segura-123'})
        self.assertTrue(get_user_model().objects.filter(email=MINIMO['email']).exists())

    def test_el_correo_repetido_no_distingue_mayusculas(self):
        get_user_model().objects.create_user(
            email='ana-reglas@example.com', username='ana-reglas@example.com', password='Clave-Segura-123',
        )
        respuesta = self.client.post(self.url, {
            **MINIMO, 'email': 'ANA-Reglas@example.com', 'password1': 'Clave-Segura-123',
        })
        self.assertContains(respuesta, 'ya está registrado')
        self.assertEqual(get_user_model().objects.count(), 1)


class RestablecimientoPorCorreoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            email='olvido-reglas@example.com', username='olvido-reglas@example.com',
            password='Clave-Vieja-123', first_name='Luis',
        )

    def test_el_correo_llega_en_espanol_con_un_enlace_que_funciona(self):
        self.client.post(reverse('password_reset'), {'email': 'olvido-reglas@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.subject, 'Restablece tu contraseña de GoToGym')
        self.assertIn('Hola Luis', correo.body)
        self.assertIn('https://gotogym.store/', correo.body)
        enlace = next(linea for linea in correo.body.splitlines() if '/accounts/reset/' in linea)
        ruta = enlace.replace('https://gotogym.store', '')
        respuesta = self.client.get(ruta, follow=True)
        self.assertContains(respuesta, 'Mínimo 8 caracteres')

    def test_la_nueva_contrasena_debe_cumplir_las_reglas(self):
        self.client.post(reverse('password_reset'), {'email': 'olvido-reglas@example.com'})
        enlace = next(linea for linea in mail.outbox[0].body.splitlines() if '/accounts/reset/' in linea)
        formulario = self.client.get(enlace.replace('https://gotogym.store', ''), follow=True)
        destino = formulario.redirect_chain[-1][0]
        debil = self.client.post(destino, {'new_password1': 'sencilla', 'new_password2': 'sencilla'})
        self.assertContains(debil, 'La contraseña debe tener')
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Clave-Vieja-123'))
        self.client.post(destino, {'new_password1': 'Clave-Nueva-456', 'new_password2': 'Clave-Nueva-456'})
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Clave-Nueva-456'))
