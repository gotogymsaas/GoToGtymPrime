"""Traducciones al ingles y portugues de las pantallas de compra y de cuenta."""
from django.test import TestCase
from django.utils import translation


class TraduccionesTests(TestCase):
    def _html(self, ruta):
        return self.client.get(ruta).content.decode()

    def test_el_carrito_vacio_se_ve_en_ingles_y_portugues(self):
        self.assertIn('Your cart is empty.', self._html('/en/carrito/'))
        self.assertIn('Seu carrinho está vazio.', self._html('/pt/carrito/'))
        self.assertIn('Tu carrito está vacío.', self._html('/es/carrito/'))

    def test_el_login_y_el_pie_estan_traducidos(self):
        en = self._html('/en/accounts/acceso/')
        pt = self._html('/pt/accounts/acceso/')
        self.assertIn('Forgot your password?', en)
        self.assertIn('Esqueceu sua senha?', pt)
        self.assertNotIn('¿Olvidaste tu contraseña?', en + pt)

    def test_recuperar_contrasena_en_los_tres_idiomas(self):
        self.assertIn('Recover your <em>access</em>', self._html('/en/accounts/password_reset/'))
        self.assertIn('Recupere seu <em>acesso</em>', self._html('/pt/accounts/password_reset/'))

    def test_los_plurales_siguen_la_regla_de_cada_idioma(self):
        from django.utils.translation import ngettext
        casos = {
            'en': ('%(counter)s product', '%(counter)s products'),
            'pt': ('%(counter)s produto', '%(counter)s produtos'),
        }
        for idioma, (uno, varios) in casos.items():
            with translation.override(idioma):
                self.assertEqual(ngettext('%(counter)s producto', '%(counter)s productos', 1), uno)
                self.assertEqual(ngettext('%(counter)s producto', '%(counter)s productos', 3), varios)

    def test_los_nombres_de_los_idiomas_no_se_traducen(self):
        from django.utils.translation import gettext
        for idioma in ('es', 'en', 'pt'):
            with translation.override(idioma):
                for nombre in ('Español', 'English', 'Português'):
                    self.assertEqual(gettext(nombre), nombre, f'{nombre} en {idioma}')

    def test_las_pantallas_de_cuenta_estan_traducidas(self):
        self.assertIn('Log in to <em>your account</em>', self._html('/en/accounts/acceso/'))
        self.assertIn('Entre na <em>sua conta</em>', self._html('/pt/accounts/acceso/'))
        self.assertIn('Create your <em>account</em>', self._html('/en/accounts/register/'))
        self.assertIn('Crie sua <em>conta</em>', self._html('/pt/accounts/register/'))
