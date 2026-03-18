from django.test import TestCase


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
