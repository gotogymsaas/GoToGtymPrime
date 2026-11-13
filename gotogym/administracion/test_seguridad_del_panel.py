"""Permisos de pedidos y usuarios, y bitacora de acciones del panel."""
import importlib
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from orders.models import Order, OrderStatus

from .models import AccionDePanel
from .permissions import ADMIN_PERM_SPECS


def _permiso(app_label, codename):
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class PermisosDePedidosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.pedido = Order.objects.create(
            order_number='GTG-SEG-0001', email='cliente@example.com', phone='3000000000',
            subtotal=Decimal('100000'), total=Decimal('100000'),
            order_status=OrderStatus.PENDING_PAYMENT,
        )
        # Un grupo acota al personal: sin grupo, el panel le da el paquete completo.
        catalogo = Group.objects.create(name='Solo catalogo')
        catalogo.permissions.add(_permiso('products', 'change_product'))
        cls.de_catalogo = User.objects.create_user(
            email='catalogo@example.com', username='catalogo@example.com', password='x', is_staff=True,
        )
        cls.de_catalogo.groups.add(catalogo)

        operacion = Group.objects.create(name='Operacion de pedidos')
        operacion.permissions.add(
            _permiso('orders', 'view_order'), _permiso('orders', 'change_order'),
            _permiso('accounts', 'view_user'),
        )
        cls.de_operacion = User.objects.create_user(
            email='operacion@example.com', username='operacion@example.com', password='x', is_staff=True,
        )
        cls.de_operacion.groups.add(operacion)

    def _cambiar_estado(self, usuario):
        self.client.force_login(usuario)
        return self.client.post(
            reverse('admin_order_update_status', args=[self.pedido.order_number]),
            {'order_status': OrderStatus.CANCELLED},
        )

    def test_personal_sin_permiso_de_pedidos_no_cambia_el_estado(self):
        self._cambiar_estado(self.de_catalogo)

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.PENDING_PAYMENT)

    def test_personal_con_permiso_de_pedidos_si_lo_cambia(self):
        self._cambiar_estado(self.de_operacion)

        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.CANCELLED)

    def test_sin_permiso_no_ve_pedidos_ni_usuarios_ni_exporta(self):
        self.client.force_login(self.de_catalogo)
        for nombre, args in (
            ('admin_orders', []), ('admin_order_detail', [self.pedido.order_number]),
            ('admin_users', []), ('admin_export_orders', []),
        ):
            with self.subTest(vista=nombre):
                respuesta = self.client.get(reverse(nombre, args=args))
                self.assertRedirects(respuesta, reverse('admin_dashboard'), fetch_redirect_response=False)

    def test_con_permiso_ve_pedidos_y_usuarios(self):
        self.client.force_login(self.de_operacion)
        for nombre, args in (
            ('admin_orders', []), ('admin_order_detail', [self.pedido.order_number]), ('admin_users', []),
        ):
            with self.subTest(vista=nombre):
                self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 200)

    def test_los_permisos_nuevos_forman_parte_del_paquete_de_administrador(self):
        for par in (('orders', 'view_order'), ('orders', 'change_order'), ('accounts', 'view_user')):
            self.assertIn(par, ADMIN_PERM_SPECS)

    def test_agregar_y_borrar_fotos_exigen_post(self):
        self.client.force_login(self.de_catalogo)
        self.assertEqual(self.client.get(reverse('admin_product_media_add', args=[1])).status_code, 405)
        self.assertEqual(self.client.get(reverse('admin_product_media_delete', args=[1, 1])).status_code, 405)


class MigracionDePermisosTests(TestCase):
    def setUp(self):
        self.migracion = importlib.import_module(
            'administracion.migrations.0009_permisos_de_pedidos_y_usuarios',
        )
        User = get_user_model()
        anteriores = [_permiso(app, codename) for app, codename in self.migracion.PAQUETE_ANTERIOR]
        self.con_paquete = User.objects.create_user(
            email='paquete@example.com', username='paquete@example.com', password='x', is_staff=True,
        )
        self.con_paquete.user_permissions.add(*anteriores)
        self.parcial = User.objects.create_user(
            email='parcial@example.com', username='parcial@example.com', password='x', is_staff=True,
        )
        self.parcial.user_permissions.add(*anteriores[:5])

    def test_quien_tenia_el_paquete_completo_recibe_los_permisos_nuevos(self):
        self.migracion.otorgar(apps, None)

        self.assertTrue(self.con_paquete.user_permissions.filter(codename='change_order').exists())
        self.assertTrue(self.con_paquete.user_permissions.filter(codename='view_user').exists())

    def test_quien_tenia_un_paquete_parcial_no_recibe_nada(self):
        self.migracion.otorgar(apps, None)

        self.assertFalse(self.parcial.user_permissions.filter(codename='change_order').exists())


class BitacoraDelPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superusuario = get_user_model().objects.create_superuser(
            email='root-bitacora@example.com', username='root-bitacora@example.com', password='x',
        )
        cls.pedido = Order.objects.create(
            order_number='GTG-BIT-0001', email='cliente@example.com', phone='3000000000',
            subtotal=Decimal('100000'), total=Decimal('100000'),
            order_status=OrderStatus.PENDING_PAYMENT,
        )

    def setUp(self):
        self.client.force_login(self.superusuario)

    def test_un_post_exitoso_deja_una_fila(self):
        self.client.post(
            reverse('admin_order_update_status', args=[self.pedido.order_number]),
            {'order_status': OrderStatus.CANCELLED},
        )

        accion = AccionDePanel.objects.get()
        self.assertEqual(accion.usuario, self.superusuario)
        self.assertEqual(accion.vista, 'order_update_status')
        self.assertEqual(accion.argumentos, {'order_number': 'GTG-BIT-0001'})

    def test_no_guarda_el_contenido_del_formulario(self):
        self.client.post(
            reverse('admin_order_update_status', args=[self.pedido.order_number]),
            {'order_status': OrderStatus.CANCELLED, 'tracking_code': 'GUIA-SECRETA-123'},
        )

        accion = AccionDePanel.objects.get()
        self.assertNotIn('GUIA-SECRETA-123', str(accion.argumentos))

    def test_una_consulta_no_deja_fila(self):
        self.client.get(reverse('admin_orders'))

        self.assertFalse(AccionDePanel.objects.exists())

    def test_un_fallo_al_escribir_la_bitacora_no_rompe_la_accion(self):
        from unittest.mock import patch

        with patch('administracion.models.AccionDePanel.objects.create', side_effect=OSError('sin disco')):
            with self.assertLogs('administracion.permissions', level='ERROR'):
                respuesta = self.client.post(
                    reverse('admin_order_update_status', args=[self.pedido.order_number]),
                    {'order_status': OrderStatus.CANCELLED},
                )

        self.assertEqual(respuesta.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.order_status, OrderStatus.CANCELLED)


class ComandoDePermisosHeredadosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.sin_grupo = User.objects.create_user(
            email='heredada@example.com', username='heredada@example.com', password='x', is_staff=True,
        )
        grupo = Group.objects.create(name='Con grupo')
        cls.con_grupo = User.objects.create_user(
            email='congrupo@example.com', username='congrupo@example.com', password='x', is_staff=True,
        )
        cls.con_grupo.groups.add(grupo)

    def _ejecutar(self, *args):
        from io import StringIO

        from django.core.management import call_command

        salida = StringIO()
        call_command('otorgar_permisos_admin_heredados', *args, stdout=salida)
        return salida.getvalue()

    def test_sin_argumentos_solo_lista_y_no_modifica(self):
        texto = self._ejecutar()

        self.assertIn('heredada@example.com', texto)
        self.assertNotIn('congrupo@example.com', texto)
        self.assertFalse(self.sin_grupo.user_permissions.exists())

    def test_otorga_solo_a_la_cuenta_indicada(self):
        self._ejecutar('--otorgar', 'heredada@example.com')

        self.assertTrue(self.sin_grupo.user_permissions.filter(codename='change_order').exists())
        self.assertFalse(self.con_grupo.user_permissions.exists())

    def test_rechaza_una_cuenta_que_no_esta_pendiente(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self._ejecutar('--otorgar', 'congrupo@example.com')
