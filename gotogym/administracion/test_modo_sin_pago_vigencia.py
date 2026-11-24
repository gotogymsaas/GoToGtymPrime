"""Modo "Confirmar sin pagar (equipo)": vence a las 24 horas, encenderlo exige
un permiso propio y avisa a Sentry en un entorno real."""
import importlib
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from gotogym import ajustes_tienda

from .models import AccionDePanel, PanelSettings


def _usuario(correo, **extra):
    return get_user_model().objects.create_user(email=correo, username=correo, password='x', **extra)


def _permiso(codename):
    return Permission.objects.get(content_type__app_label='administracion', codename=codename)


def _peticion(usuario):
    peticion = RequestFactory().get('/')
    peticion.user = usuario
    return peticion


class VigenciaDelModoTests(TestCase):
    def _encender(self):
        return PanelSettings.objects.update_or_create(pk=1, defaults={'staff_checkout_without_payment': True})[0]

    def test_al_encender_se_anota_la_fecha_y_al_apagar_se_borra(self):
        fila = self._encender()
        self.assertIsNotNone(fila.staff_checkout_without_payment_since)
        fila.staff_checkout_without_payment = False
        fila.save(update_fields=['staff_checkout_without_payment'])
        fila.refresh_from_db()
        self.assertIsNone(fila.staff_checkout_without_payment_since)

    def test_vence_a_las_24_horas_sin_tarea_periodica(self):
        fila = self._encender()
        inicio = fila.staff_checkout_without_payment_since
        self.assertTrue(ajustes_tienda.modo_sin_pago_activo())
        self.assertEqual(ajustes_tienda.modo_sin_pago_vence_el(), inicio + timedelta(hours=24))
        with patch('django.utils.timezone.now', return_value=inicio + timedelta(hours=23, minutes=59)):
            self.assertTrue(ajustes_tienda.modo_sin_pago_activo())
        with patch('django.utils.timezone.now', return_value=inicio + timedelta(hours=24, seconds=1)):
            self.assertFalse(ajustes_tienda.modo_sin_pago_activo())
            self.assertIsNone(ajustes_tienda.modo_sin_pago_vence_el())

    def test_una_marca_sin_fecha_cuenta_como_vencida(self):
        self._encender()
        PanelSettings.objects.filter(pk=1).update(staff_checkout_without_payment_since=None)
        self.assertFalse(ajustes_tienda.modo_sin_pago_activo())

    def test_leer_todos_sigue_siendo_una_sola_consulta(self):
        self._encender()
        with self.assertNumQueries(1):
            ajustes_tienda._leer_todos()

    def test_un_cliente_nunca_confirma_sin_pagar_con_el_interruptor_encendido(self):
        self._encender()
        cliente = _usuario('cliente-vigencia@example.com')
        self.assertTrue(ajustes_tienda.modo_sin_pago_activo())
        self.assertFalse(ajustes_tienda.confirma_sin_pagar(_peticion(cliente)))
        self.assertFalse(ajustes_tienda.confirma_sin_pagar(_peticion(AnonymousUser())))
        equipo = _usuario('equipo-vigencia@example.com', is_staff=True)
        self.assertTrue(ajustes_tienda.confirma_sin_pagar(_peticion(equipo)))

    def test_el_equipo_deja_de_confirmar_sin_pagar_al_vencer(self):
        fila = self._encender()
        equipo = _usuario('equipo-vence@example.com', is_staff=True)
        despues = fila.staff_checkout_without_payment_since + timedelta(hours=25)
        with patch('django.utils.timezone.now', return_value=despues):
            self.assertFalse(ajustes_tienda.confirma_sin_pagar(_peticion(equipo)))

    def test_el_panel_muestra_cuando_vence(self):
        self._encender()
        admin = get_user_model().objects.create_superuser(
            email='root-vence@example.com', username='root-vence@example.com', password='x',
        )
        self.client.force_login(admin)
        vence = ajustes_tienda.modo_sin_pago_vence_el()
        respuesta = self.client.get(reverse('admin_dashboard'))
        self.assertContains(respuesta, 'Se apaga solo el')
        self.assertContains(respuesta, timezone.localtime(vence).strftime('%d/%m/%Y %H:%M'))


class PermisoParaEncenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('admin_staff_checkout_without_payment_toggle')
        # Con grupo: una cuenta de staff sin grupo se trata como administrador
        # heredado y el panel le completa el paquete entero, permiso incluido.
        rol_cambio = Group.objects.create(name='rol-cambio')
        rol_cambio.permissions.add(_permiso('change_panelsettings'))
        rol_ambos = Group.objects.create(name='rol-ambos')
        rol_ambos.permissions.add(_permiso('change_panelsettings'), _permiso('toggle_test_mode'))
        cls.con_cambio = _usuario('cambio@example.com', is_staff=True)
        cls.con_cambio.groups.add(rol_cambio)
        cls.con_ambos = _usuario('ambos@example.com', is_staff=True)
        cls.con_ambos.groups.add(rol_ambos)

    def test_solo_con_change_panelsettings_no_puede_encender(self):
        self.client.force_login(self.con_cambio)
        with patch('administracion.views.sentry_sdk.capture_message') as sentry:
            self.client.post(self.url, {'activar': '1'})
        self.assertFalse(PanelSettings.load().staff_checkout_without_payment)
        sentry.assert_not_called()

    def test_el_intento_sin_permiso_queda_en_la_bitacora(self):
        self.client.force_login(self.con_cambio)
        self.client.post(self.url, {'activar': '1'})
        accion = AccionDePanel.objects.get()
        self.assertEqual(accion.argumentos, {'activar': '1', 'resultado': 'sin_permiso'})

    def test_con_el_permiso_propio_enciende_y_queda_en_la_bitacora(self):
        self.client.force_login(self.con_ambos)
        self.client.post(self.url, {'activar': '1'})
        self.assertTrue(ajustes_tienda.modo_sin_pago_activo())
        accion = AccionDePanel.objects.get()
        self.assertEqual(accion.vista, 'staff_checkout_without_payment_toggle')
        self.assertEqual(accion.usuario, self.con_ambos)
        self.assertEqual(accion.argumentos, {'activar': '1'})

    def test_apagar_sigue_permitido_con_change_panelsettings(self):
        self.client.force_login(self.con_ambos)
        self.client.post(self.url, {'activar': '1'})
        self.client.force_login(self.con_cambio)
        self.client.post(self.url, {'activar': '0'})
        self.assertFalse(ajustes_tienda.modo_sin_pago_activo())
        self.assertFalse(PanelSettings.load().staff_checkout_without_payment)

    def test_encenderlo_otra_vez_tras_vencer_renueva_el_plazo(self):
        self.client.force_login(self.con_ambos)
        self.client.post(self.url, {'activar': '1'})
        antes = PanelSettings.load().staff_checkout_without_payment_since
        with patch('django.utils.timezone.now', return_value=antes + timedelta(hours=30)):
            self.assertFalse(ajustes_tienda.modo_sin_pago_activo())
            self.client.post(self.url, {'activar': '1'})
            self.assertTrue(ajustes_tienda.modo_sin_pago_activo())
        self.assertGreater(PanelSettings.load().staff_checkout_without_payment_since, antes)

    def test_el_boton_para_encender_solo_se_ofrece_con_el_permiso(self):
        self.client.force_login(self.con_cambio)
        self.assertNotContains(self.client.get(reverse('admin_dashboard')), 'Confirmar sin pagar (equipo)')
        self.client.force_login(self.con_ambos)
        self.assertContains(self.client.get(reverse('admin_dashboard')), 'Confirmar sin pagar (equipo)')


class AvisoASentryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            email='root-sentry@example.com', username='root-sentry@example.com', password='x',
        )

    def test_encender_fuera_de_debug_emite_un_aviso_solo_con_el_id_del_usuario(self):
        self.client.force_login(self.admin)
        with override_settings(DEBUG=False), \
                patch('administracion.views.sentry_sdk.capture_message') as capturar, \
                patch('administracion.views.sentry_sdk.new_scope') as nuevo_ambito:
            self.client.post(reverse('admin_staff_checkout_without_payment_toggle'), {'activar': '1'})
        capturar.assert_called_once()
        self.assertEqual(capturar.call_args.kwargs['level'], 'warning')
        mensaje = capturar.call_args.args[0]
        self.assertNotIn(self.admin.email, mensaje)
        usuario = nuevo_ambito.return_value.__enter__.return_value.set_user.call_args.args[0]
        self.assertEqual(usuario, {'id': str(self.admin.pk)})

    def test_con_debug_no_emite_nada(self):
        self.client.force_login(self.admin)
        with override_settings(DEBUG=True), patch('administracion.views.sentry_sdk.capture_message') as capturar:
            self.client.post(reverse('admin_staff_checkout_without_payment_toggle'), {'activar': '1'})
        capturar.assert_not_called()

    def test_apagar_no_emite_nada(self):
        self.client.force_login(self.admin)
        with override_settings(DEBUG=False), patch('administracion.views.sentry_sdk.capture_message') as capturar:
            self.client.post(reverse('admin_staff_checkout_without_payment_toggle'), {'activar': '0'})
        capturar.assert_not_called()


class MigracionDelPermisoTests(TestCase):
    def setUp(self):
        self.migracion = importlib.import_module('administracion.migrations.0013_otorgar_permiso_modo_de_pruebas')

    def test_los_grupos_y_cuentas_con_change_panelsettings_reciben_el_permiso_nuevo(self):
        con_cambio = Group.objects.create(name='con-cambio')
        con_cambio.permissions.add(_permiso('change_panelsettings'))
        sin_cambio = Group.objects.create(name='sin-cambio')
        sin_cambio.permissions.add(_permiso('view_panelsettings'))
        cuenta = _usuario('directa@example.com', is_staff=True)
        cuenta.user_permissions.add(_permiso('change_panelsettings'))
        otra = _usuario('otra@example.com', is_staff=True)

        self.migracion.otorgar(apps, None)

        nuevo = _permiso('toggle_test_mode')
        self.assertIn(nuevo, con_cambio.permissions.all())
        self.assertNotIn(nuevo, sin_cambio.permissions.all())
        self.assertIn(nuevo, cuenta.user_permissions.all())
        self.assertNotIn(nuevo, otra.user_permissions.all())

    def test_el_modo_que_ya_estaba_encendido_recibe_fecha_para_vencer(self):
        PanelSettings.objects.create(pk=1)
        PanelSettings.objects.filter(pk=1).update(staff_checkout_without_payment=True)
        self.migracion.otorgar(apps, None)
        fila = PanelSettings.objects.get(pk=1)
        self.assertEqual(fila.staff_checkout_without_payment_since, fila.updated_at)

    def test_el_paquete_de_administrador_incluye_el_permiso(self):
        from .permissions import ADMIN_PERM_SPECS

        self.assertIn(('administracion', 'toggle_test_mode'), ADMIN_PERM_SPECS)
