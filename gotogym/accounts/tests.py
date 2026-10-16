from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class BasicRoutesSmokeTests(TestCase):
	def test_home_page_es(self):
		response = self.client.get('/es/')
		self.assertEqual(response.status_code, 200)

	def test_login_page_es(self):
		response = self.client.get('/es/accounts/login/')
		self.assertEqual(response.status_code, 200)

	def test_crm_healthz(self):
		response = self.client.get('/healthz')
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'OK')


class LogoutRedirectTests(TestCase):
	"""El boton "Salir" del panel admin manda un `next` a la tienda; el
	logout normal del resto del sitio (sin `next`) sigue yendo a home,
	como siempre."""

	def setUp(self):
		User = get_user_model()
		self.usuario = User.objects.create_user(
			email='logout-test@example.com', username='logout-test@example.com', password='secret123',
		)
		self.client.force_login(self.usuario)

	def test_logout_sin_next_va_a_home(self):
		response = self.client.post(reverse('logout'))
		self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

	def test_logout_con_next_seguro_respeta_el_destino(self):
		response = self.client.post(reverse('logout'), {'next': reverse('tienda:producto_list')})
		self.assertRedirects(response, reverse('tienda:producto_list'), fetch_redirect_response=False)

	def test_logout_ignora_un_next_hacia_otro_dominio(self):
		response = self.client.post(reverse('logout'), {'next': 'https://evil.example.com/'})
		self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)


class RegistroDuranteLaCompraTests(TestCase):
	DATOS = {
		'first_name': 'Ana', 'last_name': 'Prueba', 'age': '30',
		'email': 'nueva@example.com', 'password1': 'Secret-12345', 'password2': 'Secret-12345',
		'accepted_terms': 'on',
	}

	def test_registro_inicia_sesion_y_sigue_al_destino(self):
		destino = reverse('orders:checkout')
		response = self.client.post(reverse('register'), {**self.DATOS, 'next': destino})
		self.assertRedirects(response, destino, fetch_redirect_response=False)
		self.assertIn('_auth_user_id', self.client.session)

	def test_registro_sin_next_va_a_la_home(self):
		response = self.client.post(reverse('register'), self.DATOS)
		self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

	def test_registro_ignora_un_next_hacia_otro_dominio(self):
		response = self.client.post(reverse('register'), {**self.DATOS, 'next': 'https://evil.example.com/'})
		self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

	def test_login_desde_checkout_muestra_aviso(self):
		response = self.client.get(reverse('commercial_login'), {'next': reverse('orders:checkout')})
		self.assertContains(response, 'Tu carrito se conserva')
