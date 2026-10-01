"""Libreta de direcciones del cliente (G4): guardar, editar, marcar
predeterminada y borrar, sin afectar direcciones de pedidos ya hechos."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CustomerAddress, CustomerSegment

DATOS_DIRECCION = {
    'label': 'Casa', 'full_name': 'Ana Marin', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}

# Lo que realmente acepta el formulario hoy (`label`/`full_name`/`phone` se
# completan a partir del perfil del usuario, ver `accounts.views.address_edit`).
DATOS_DIRECCION_FORMULARIO = {
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


class LibretaDeDireccionesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            email='direcciones@example.com', username='direcciones@example.com', password='secret123',
        )
        self.otro_usuario = User.objects.create_user(
            email='otro-direcciones@example.com', username='otro-direcciones@example.com', password='secret123',
        )
        self.client.force_login(self.usuario)

    def test_crear_direccion(self):
        self.client.post(reverse('address_new'), DATOS_DIRECCION_FORMULARIO)
        self.assertEqual(CustomerAddress.objects.filter(user=self.usuario).count(), 1)

    def test_la_primera_direccion_queda_predeterminada_automaticamente(self):
        self.client.post(reverse('address_new'), DATOS_DIRECCION_FORMULARIO)
        direccion = CustomerAddress.objects.get(user=self.usuario)
        self.assertTrue(direccion.is_default)

    def test_el_nombre_y_telefono_se_completan_desde_el_perfil_no_del_formulario(self):
        self.usuario.first_name = 'Ana'
        self.usuario.last_name = 'Marin'
        self.usuario.phone = '3009998888'
        self.usuario.save()

        self.client.post(reverse('address_new'), DATOS_DIRECCION_FORMULARIO)

        direccion = CustomerAddress.objects.get(user=self.usuario)
        self.assertEqual(direccion.full_name, 'Ana Marin')
        self.assertEqual(direccion.phone, '3009998888')

    def test_marcar_como_predeterminada_desmarca_las_demas(self):
        d1 = CustomerAddress.objects.create(user=self.usuario, is_default=True, **DATOS_DIRECCION)
        d2 = CustomerAddress.objects.create(user=self.usuario, is_default=False, **DATOS_DIRECCION)

        self.client.post(reverse('address_set_default', args=[d2.pk]))

        d1.refresh_from_db()
        d2.refresh_from_db()
        self.assertFalse(d1.is_default)
        self.assertTrue(d2.is_default)

    def test_una_segunda_direccion_nueva_no_desplaza_la_predeterminada(self):
        # La predeterminada ahora se elige solo desde la lista de
        # direcciones (`address_set_default`); crear una direccion nueva ya
        # no la cambia por si sola, ni siquiera si ya existe una por defecto.
        anterior = CustomerAddress.objects.create(user=self.usuario, is_default=True, **DATOS_DIRECCION)

        self.client.post(reverse('address_new'), DATOS_DIRECCION_FORMULARIO)

        anterior.refresh_from_db()
        self.assertTrue(anterior.is_default)
        self.assertEqual(CustomerAddress.objects.filter(user=self.usuario, is_default=True).count(), 1)

    def test_no_se_puede_editar_la_direccion_de_otro_usuario(self):
        ajena = CustomerAddress.objects.create(user=self.otro_usuario, **DATOS_DIRECCION)
        response = self.client.get(reverse('address_edit', args=[ajena.pk]))
        self.assertEqual(response.status_code, 404)

    def test_no_se_puede_borrar_la_direccion_de_otro_usuario(self):
        ajena = CustomerAddress.objects.create(user=self.otro_usuario, **DATOS_DIRECCION)
        self.client.post(reverse('address_delete', args=[ajena.pk]))
        self.assertTrue(CustomerAddress.objects.filter(pk=ajena.pk).exists())

    def test_ciudad_invalida_para_el_departamento_no_se_guarda(self):
        datos = dict(DATOS_DIRECCION, department='Antioquia', city='Ciudad Inexistente')
        self.client.post(reverse('address_new'), datos)
        self.assertEqual(CustomerAddress.objects.filter(user=self.usuario).count(), 0)

    def test_libreta_exige_login(self):
        self.client.logout()
        response = self.client.get(reverse('address_book'))
        self.assertEqual(response.status_code, 302)


class SegmentoDeClienteTests(TestCase):
    def test_un_usuario_puede_pertenecer_a_varios_segmentos(self):
        User = get_user_model()
        usuario = User.objects.create_user(
            email='segmento@example.com', username='segmento@example.com', password='secret123',
        )
        mayorista = CustomerSegment.objects.create(name='Mayorista')
        entrenador = CustomerSegment.objects.create(name='Entrenador')

        usuario.customer_segments.add(mayorista, entrenador)

        self.assertEqual(usuario.customer_segments.count(), 2)
        self.assertIn(usuario, mayorista.members.all())
