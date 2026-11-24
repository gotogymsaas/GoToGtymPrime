"""La pantalla del panel: permisos y el boton "Reintentar"."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tareas.models import EstadoTarea, TareaPendiente


def _usuario(correo, *codigos, staff=True, superusuario=False):
    User = get_user_model()
    if superusuario:
        return User.objects.create_superuser(email=correo, username=correo, password='secret123')
    usuario = User.objects.create_user(email=correo, username=correo, password='secret123', is_staff=staff)
    for codigo in codigos:
        usuario.user_permissions.add(Permission.objects.get(content_type__app_label='tareas', codename=codigo))
    return usuario


class PantallaDeTareasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fallida = TareaPendiente.objects.create(
            ruta='orders.correos.pedido_recibido', estado=EstadoTarea.FALLIDA, intentos=5,
            ultimo_error='OSError: servidor caido', terminada=timezone.now(),
        )
        cls.pendiente = TareaPendiente.objects.create(ruta='afiliados.correos.afiliado_aprobado')
        cls.hecha = TareaPendiente.objects.create(ruta='orders.correos.pedido_enviado', estado=EstadoTarea.HECHA)
        cls.url = reverse('admin_tareas')

    def reintentar(self, tarea):
        return self.client.post(reverse('admin_tarea_reintentar', args=[tarea.pk]))

    def test_un_anonimo_va_al_acceso(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_un_cliente_sin_panel_recibe_403(self):
        self.client.force_login(_usuario('cliente@example.com', 'view_tareapendiente', staff=False))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_un_staff_sin_el_permiso_recibe_403(self):
        self.client.force_login(_usuario('staff@example.com'))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_con_el_permiso_de_ver_muestra_fallidas_y_pendientes(self):
        self.client.force_login(_usuario('ver@example.com', 'view_tareapendiente'))
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'orders.correos.pedido_recibido')
        self.assertContains(r, 'OSError: servidor caido')
        self.assertContains(r, 'afiliados.correos.afiliado_aprobado')
        self.assertNotContains(r, 'orders.correos.pedido_enviado')

    def test_sin_el_permiso_de_reintentar_no_ve_el_boton(self):
        self.client.force_login(_usuario('ver@example.com', 'view_tareapendiente'))
        self.assertNotContains(self.client.get(self.url), 'Reintentar')

    def test_con_el_permiso_de_reintentar_ve_el_boton(self):
        self.client.force_login(_usuario('op@example.com', 'view_tareapendiente', 'retry_tarea'))
        self.assertContains(self.client.get(self.url), 'Reintentar')

    def test_reintentar_sin_el_permiso_recibe_403_y_no_cambia_nada(self):
        self.client.force_login(_usuario('ver@example.com', 'view_tareapendiente'))
        self.assertEqual(self.reintentar(self.fallida).status_code, 403)
        self.fallida.refresh_from_db()
        self.assertEqual(self.fallida.estado, EstadoTarea.FALLIDA)

    def test_reintentar_solo_acepta_post(self):
        self.client.force_login(_usuario('op@example.com', 'view_tareapendiente', 'retry_tarea'))
        r = self.client.get(reverse('admin_tarea_reintentar', args=[self.fallida.pk]))
        self.assertEqual(r.status_code, 405)

    def test_reintentar_devuelve_la_tarea_a_la_cola(self):
        self.client.force_login(_usuario('op@example.com', 'retry_tarea', 'view_tareapendiente'))
        r = self.reintentar(self.fallida)
        self.assertRedirects(r, self.url, fetch_redirect_response=False)
        self.fallida.refresh_from_db()
        self.assertEqual(self.fallida.estado, EstadoTarea.PENDIENTE)
        self.assertEqual(self.fallida.intentos, 0)

    def test_reintentar_una_que_no_esta_fallida_no_cambia_nada(self):
        self.client.force_login(_usuario('op@example.com', 'retry_tarea'))
        self.reintentar(self.hecha)
        self.hecha.refresh_from_db()
        self.assertEqual(self.hecha.estado, EstadoTarea.HECHA)

    def test_un_superusuario_pasa_sin_permisos_explicitos(self):
        self.client.force_login(_usuario('root@example.com', superusuario=True))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.reintentar(self.fallida).status_code, 302)
        self.fallida.refresh_from_db()
        self.assertEqual(self.fallida.estado, EstadoTarea.PENDIENTE)
