"""Entrar, registrarse y recuperar la contraseña se sienten parte de la tienda:
conservan el menu y el pie, muestran lo que hay en el carrito y el registro
pide solo lo necesario para comprar."""
from decimal import Decimal

from carrito.services import CART_VERSION, SESSION_CART_KEY, SESSION_VERSION_KEY
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

CLAVE = 'clave-segura-123'


class ChromeDelSitioTests(TestCase):
    RUTAS = ('commercial_login', 'register', 'password_reset', 'password_reset_done', 'password_reset_complete')

    def test_conservan_menu_y_pie_de_la_tienda(self):
        for nombre in self.RUTAS:
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertIn('class="gtg-navbar"', html, nombre)
            self.assertIn('class="gtg-footer"', html, nombre)
            self.assertIn(reverse('tienda:producto_list'), html, nombre)

    def test_tienen_cabecera_editorial_con_titular_visible(self):
        for nombre in self.RUTAS:
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertIn('commercial-auth__kicker', html, nombre)
            self.assertEqual(html.count('<h1'), 1, nombre)
            self.assertIn('commercial-auth__title', html, nombre)
            self.assertNotIn('commercial-auth__sr-only', html, nombre)

    def test_siguen_sin_indexarse(self):
        for nombre in self.RUTAS:
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertIn('<meta name="robots" content="noindex, nofollow">', html, nombre)

    def test_la_escena_orbital_se_conserva_como_acento(self):
        html = self.client.get(reverse('commercial_login')).content.decode()
        self.assertIn('commercial-auth__scene', html)
        self.assertIn('aria-hidden="true"', html)


class ResumenDelCarritoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria cuenta')
        marca = Brand.objects.create(name='Marca cuenta')
        producto = Product.objects.create(
            name='Producto cuenta', category=categoria, brand=marca, base_price=Decimal('100000'), stock=0,
        )
        cls.variante = ProductVariant.objects.create(product=producto, sku='CTA-1', size='S', color='negro')
        Inventory.objects.create(variant=cls.variante, quantity_available=5)

    def _llenar_carrito(self, cantidad=2):
        sesion = self.client.session
        sesion[SESSION_CART_KEY] = {str(self.variante.pk): cantidad}
        sesion[SESSION_VERSION_KEY] = CART_VERSION
        sesion.save()

    def test_con_articulos_se_muestra_junto_al_formulario(self):
        self._llenar_carrito(2)
        for nombre in ('commercial_login', 'register'):
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertIn('commercial-auth__summary', html, nombre)
            self.assertIn('2 artículos', html, nombre)
            self.assertIn('$200.000 COP', html, nombre)
            self.assertIn(reverse('carrito:cart_detail'), html, nombre)

    def test_un_solo_articulo_va_en_singular(self):
        self._llenar_carrito(1)
        html = self.client.get(reverse('commercial_login')).content.decode()
        self.assertRegex(html, r'1 artículo\s')
        self.assertNotIn('1 artículos', html)

    def test_sin_articulos_no_aparece(self):
        for nombre in ('commercial_login', 'register'):
            self.assertNotIn('commercial-auth__summary', self.client.get(reverse(nombre)).content.decode())

    def test_un_carrito_de_otra_version_se_ignora_y_no_se_borra(self):
        sesion = self.client.session
        sesion[SESSION_CART_KEY] = {str(self.variante.pk): 3}
        sesion[SESSION_VERSION_KEY] = CART_VERSION - 1
        sesion.save()
        html = self.client.get(reverse('commercial_login')).content.decode()
        self.assertNotIn('commercial-auth__summary', html)
        self.assertEqual(self.client.session[SESSION_CART_KEY], {str(self.variante.pk): 3})

    def test_el_registro_conserva_el_carrito(self):
        self._llenar_carrito(2)
        self.client.post(reverse('register'), {
            'first_name': 'Ana', 'email': 'ana-carrito@example.com', 'password1': CLAVE, 'accepted_terms': 'on',
            'next': reverse('orders:checkout'),
        })
        self.assertEqual(self.client.session[SESSION_CART_KEY], {str(self.variante.pk): 2})


class RegistroMinimoTests(TestCase):
    MINIMO = {'first_name': 'Ana', 'email': 'ana@example.com', 'password1': CLAVE, 'accepted_terms': 'on'}

    def test_el_formulario_pide_solo_nombre_correo_y_contrasena(self):
        html = self.client.get(reverse('register')).content.decode()
        for campo in ('first_name', 'email', 'password1', 'accepted_terms'):
            self.assertIn(f'name="{campo}"', html, campo)
        for campo in ('last_name', 'age', 'password2'):
            self.assertNotIn(f'name="{campo}"', html, campo)

    def test_se_registra_sin_apellido_edad_ni_confirmacion(self):
        respuesta = self.client.post(reverse('register'), self.MINIMO)
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)
        usuario = get_user_model().objects.get(email='ana@example.com')
        self.assertEqual((usuario.first_name, usuario.last_name, usuario.age), ('Ana', '', None))
        self.assertTrue(usuario.check_password(CLAVE))
        self.assertIn('_auth_user_id', self.client.session)

    def test_si_llegan_apellido_y_edad_se_guardan(self):
        self.client.post(reverse('register'), {**self.MINIMO, 'last_name': 'Soto', 'age': '31'})
        usuario = get_user_model().objects.get(email='ana@example.com')
        self.assertEqual((usuario.last_name, usuario.age), ('Soto', 31))

    def test_una_edad_que_no_es_numero_se_rechaza_sin_romper(self):
        respuesta = self.client.post(reverse('register'), {**self.MINIMO, 'age': 'treinta'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(email='ana@example.com').exists())

    def test_si_llega_confirmacion_debe_coincidir(self):
        respuesta = self.client.post(reverse('register'), {**self.MINIMO, 'password2': 'otra'})
        self.assertContains(respuesta, 'Las contraseñas no coinciden.')
        self.assertFalse(get_user_model().objects.filter(email='ana@example.com').exists())

    def test_los_errores_se_ven_en_la_pagina_y_se_conservan_los_datos(self):
        get_user_model().objects.create_user(email='ana@example.com', username='ana@example.com', password=CLAVE)
        respuesta = self.client.post(reverse('register'), {**self.MINIMO, 'first_name': 'Ana María'})
        self.assertContains(respuesta, 'El correo ya está registrado.')
        self.assertContains(respuesta, 'role="alert"')
        self.assertContains(respuesta, 'value="Ana María"')
        self.assertContains(respuesta, 'value="ana@example.com"')
        self.assertNotContains(respuesta, CLAVE)

    def test_faltan_datos_obligatorios(self):
        respuesta = self.client.post(reverse('register'), {**self.MINIMO, 'password1': ''})
        self.assertContains(respuesta, 'Completa tu nombre, correo y contraseña')

    def test_el_enlace_para_iniciar_sesion_lleva_el_destino(self):
        destino = reverse('orders:checkout')
        html = self.client.get(reverse('register'), {'next': destino}).content.decode()
        self.assertIn(f'{reverse("commercial_login")}?next=', html)

    def test_el_perfil_permite_completar_apellido_y_edad_despues(self):
        self.client.post(reverse('register'), self.MINIMO)
        html = self.client.get(reverse('edit_profile')).content.decode()
        self.assertIn('name="last_name"', html)
        self.assertIn('name="age"', html)


class DestinoTrasEntrarTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            email='dest@example.com', username='dest@example.com', password=CLAVE,
        )

    def test_next_hacia_el_propio_login_lleva_a_la_portada(self):
        respuesta = self.client.post(reverse('commercial_login'), {
            'username': 'dest@example.com', 'password': CLAVE, 'next': reverse('commercial_login'),
        })
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)

    def test_next_hacia_el_registro_lleva_a_la_portada(self):
        respuesta = self.client.post(reverse('register'), {
            'first_name': 'Eva', 'email': 'eva@example.com', 'password1': CLAVE, 'accepted_terms': 'on',
            'next': reverse('register'),
        })
        self.assertRedirects(respuesta, reverse('home'), fetch_redirect_response=False)

    def test_un_next_normal_se_respeta(self):
        destino = reverse('tienda:producto_list')
        respuesta = self.client.post(reverse('commercial_login'), {
            'username': 'dest@example.com', 'password': CLAVE, 'next': destino,
        })
        self.assertRedirects(respuesta, destino, fetch_redirect_response=False)
