"""Los correos del pedido con la cola en base de datos: salen cuando el servidor
de correo vuelve y un reintento no los duplica."""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from tareas import ejecucion
from tareas.models import EfectoAplicado, EstadoTarea, TareaPendiente

from .services import confirm_payment, create_order_from_cart
from .test_confirm_payment import DATOS, ConfirmPaymentBaseTestCase, _FakeTransaction


@override_settings(TASK_BACKEND='tareas.backend.DatabaseBackend')
class CorreosConColaTests(ConfirmPaymentBaseTestCase):
    def _procesar(self, desplazamiento_segundos=0):
        ahora = timezone.now() + timedelta(seconds=desplazamiento_segundos)
        return ejecucion.procesar_pendientes(ahora=ahora)

    def test_crear_el_pedido_solo_encola_y_el_correo_sale_al_correr_el_trabajador(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        self.assertEqual(len(mail.outbox), 0)
        tarea = TareaPendiente.objects.get()
        self.assertEqual(tarea.ruta, 'orders.correos.pedido_recibido')
        self.assertEqual(tarea.argumentos['args'], [pedido.pk])
        self._procesar(5)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [DATOS['email']])

    def test_con_el_servidor_caido_la_tarea_se_reprograma_y_sale_cuando_vuelve(self):
        create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        with patch('orders.correos.enviar_correo', side_effect=OSError('smtp caido')):
            with self.assertLogs('tareas.ejecucion', level='WARNING'), \
                    self.assertLogs('orders.correos', level='ERROR'):
                self._procesar(5)
        tarea = TareaPendiente.objects.get()
        self.assertEqual(tarea.estado, EstadoTarea.PENDIENTE)
        self.assertEqual(len(mail.outbox), 0)
        self._procesar(120)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(TareaPendiente.objects.get().estado, EstadoTarea.HECHA)

    def test_si_el_trabajador_muere_tras_enviar_el_reintento_no_duplica_el_correo(self):
        create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        ahora = timezone.now() + timedelta(seconds=5)
        tarea = ejecucion.reclamar_siguiente(ahora)
        from tareas.idempotencia import tarea_en_curso

        from . import correos
        with tarea_en_curso(tarea):
            correos.pedido_recibido(tarea.argumentos['args'][0])  # envia y el trabajador muere
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EfectoAplicado.objects.count(), 1)
        ejecucion.procesar_pendientes(ahora=ahora + timedelta(hours=1))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(TareaPendiente.objects.get().estado, EstadoTarea.HECHA)

    def test_reintentar_desde_el_panel_no_reenvia_un_correo_ya_enviado(self):
        create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        self._procesar(5)
        tarea = TareaPendiente.objects.get()
        TareaPendiente.objects.update(estado=EstadoTarea.FALLIDA)
        ejecucion.reintentar(tarea.pk, ahora=timezone.now())
        self._procesar(10)
        self.assertEqual(len(mail.outbox), 1)

    def test_dos_hechos_iguales_en_pedidos_distintos_envian_cada_uno_su_correo(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        confirm_payment(pedido, _FakeTransaction('approved'))
        self._procesar(5)
        asuntos = sorted(correo.subject for correo in mail.outbox)
        self.assertEqual(len(asuntos), len(set(asuntos)))
        self.assertGreaterEqual(len(mail.outbox), 2)
