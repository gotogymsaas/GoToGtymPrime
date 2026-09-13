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
		response = self.client.get('/es/crm/healthz')
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'OK')


class DeveloperApiLoginTests(TestCase):
	def test_active_commercial_user_can_login_to_developer_api(self):
		User = get_user_model()
		User.objects.create_user(
			email='cliente@example.com',
			username='cliente@example.com',
			password='secret123',
			is_active=True,
		)

		response = self.client.post(
			reverse('developer_login'),
			{
				'username': 'cliente@example.com',
				'email': 'cliente@example.com',
				'password': 'secret123',
			},
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertIn('access', response.json())
		self.assertEqual(response.json()['user']['role'], 'user')

	def test_inactive_user_cannot_login_to_developer_api(self):
		User = get_user_model()
		User.objects.create_user(
			email='inactivo@example.com',
			username='inactivo@example.com',
			password='secret123',
			is_active=False,
		)

		response = self.client.post(
			reverse('developer_login'),
			{
				'username': 'inactivo@example.com',
				'email': 'inactivo@example.com',
				'password': 'secret123',
			},
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 400)

	def test_developer_console_primary_login_route_accepts_commercial_user(self):
		User = get_user_model()
		User.objects.create_user(
			email='developers@example.com',
			username='developers@example.com',
			password='secret123',
			is_active=True,
		)

		response = self.client.post(
			reverse('developer_auth_login'),
			{
				'username': 'developers@example.com',
				'email': 'developers@example.com',
				'password': 'secret123',
			},
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertIn('access', response.json())
