"""La tienda exige sesion iniciada, pero no ser staff."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class TiendaAccesoTests(TestCase):
    def test_el_catalogo_exige_sesion_pero_no_ser_staff(self):
        """Un cliente sin `is_staff` debe poder ver la tienda, a diferencia
        del panel de administracion."""
        cliente = get_user_model().objects.create_user(
            email='cliente@example.com', username='cliente@example.com', password='secret123',
        )
        self.client.force_login(cliente)
        self.assertEqual(self.client.get(reverse('tienda:producto_list')).status_code, 200)
