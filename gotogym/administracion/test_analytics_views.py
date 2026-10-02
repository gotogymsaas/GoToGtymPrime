"""Panel con las definiciones nuevas, pagina de analitica y exportacion."""
import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from orders.models import OrderStatus
from orders.services import apply_order_status_transition

from administracion.views import _celda_segura, _rango_de_fechas

from .models import PanelSettings
from .test_metrics import MetricasBase


class PanelConDefinicionesNuevasTests(MetricasBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff = get_user_model().objects.create_user(
            email='v-staff@example.com', username='v-staff', password='x', is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def test_muestra_ingreso_neto_ticket_y_comparacion(self):
        self._venta(self.ana, [(self.v_caro, 1)])
        self._venta(self.luis, [(self.v_caro, 2)], dias_atras=40)  # cae en el periodo anterior
        respuesta = self.client.get(reverse('admin_dashboard'))
        self.assertContains(respuesta, 'Ingreso neto')
        self.assertContains(respuesta, 'Ticket promedio')
        # Hoy 1 pedido frente a 1 en el periodo anterior, pero con la mitad de ingreso.
        self.assertEqual(respuesta.context['comparacion']['pedidos'], 0.0)
        self.assertLess(respuesta.context['comparacion']['neto'], 0)
        self.assertContains(respuesta, 'frente al periodo anterior')

    def test_sin_periodo_anterior_lo_dice_en_vez_de_inventar_una_variacion(self):
        self._venta(self.ana, [(self.v_caro, 1)])
        html = self.client.get(reverse('admin_dashboard')).content.decode()
        self.assertIn('Sin periodo anterior para comparar', html)

    def test_un_pedido_cancelado_no_suma_y_genera_alerta_de_reembolso(self):
        pedido = self._venta(self.ana, [(self.v_caro, 1)])
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        respuesta = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(respuesta.context['resumen']['pedidos'], 0)
        self.assertEqual(respuesta.context['anuladas']['por_devolver_pedidos'], 1)
        self.assertContains(respuesta, 'anulados sin reembolso')
        self.assertContains(respuesta, 'Sin ventas en este rango.')

    def test_la_meta_se_mide_sobre_el_mes_y_no_sobre_el_rango_filtrado(self):
        PanelSettings.objects.update_or_create(pk=1, defaults={'monthly_sales_goal': Decimal('9000000')})
        self._venta(self.ana, [(self.v_caro, 1)])
        # Un rango de un solo dia no cambia el avance mensual.
        un_dia = self.client.get(reverse('admin_dashboard'), {
            'desde': str(self.hoy - timedelta(days=1)), 'hasta': str(self.hoy - timedelta(days=1)),
        })
        self.assertIsNotNone(un_dia.context['meta_mes'])
        self.assertGreater(un_dia.context['meta_mes']['acumulado'], 0)
        self.assertContains(un_dia, 'Meta de ventas del mes')

    def test_un_rango_absurdo_se_acota(self):
        respuesta = self.client.get(reverse('admin_dashboard'), {'desde': '1990-01-01', 'hasta': str(self.hoy)})
        self.assertEqual(len(respuesta.context['serie_diaria']), 366)

    def test_rango_invertido_se_ordena(self):
        peticion = RequestFactory().get('/', {'desde': '2026-10-10', 'hasta': '2026-10-01'})
        desde, hasta = _rango_de_fechas(peticion)
        self.assertLess(desde, hasta)

    def test_anonimo_no_ve_el_panel_ni_la_exportacion(self):
        self.client.logout()
        for nombre in ('admin_dashboard', 'admin_analytics', 'admin_export_orders'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 302, nombre)


class PaginaDeAnaliticaTests(MetricasBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff = get_user_model().objects.create_user(
            email='a-staff@example.com', username='a-staff', password='x', is_staff=True,
        )

    def test_cliente_comun_no_entra(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse('admin_analytics')).status_code, 302)

    def test_renderiza_todas_las_secciones_aunque_no_haya_datos(self):
        self.client.force_login(self.staff)
        respuesta = self.client.get(reverse('admin_analytics'))
        self.assertEqual(respuesta.status_code, 200)
        for texto in (
            'Embudo de compra', 'Canales de entrada', 'Busquedas internas', 'Clientes',
            'Rendimiento de cupones', 'Operacion de pedidos', 'Cobertura de inventario',
            'Todavia no hay sesiones medidas',
        ):
            self.assertContains(respuesta, texto)

    def test_con_datos_muestra_embudo_y_cobertura(self):
        from analitica.models import EventoAnalitica
        for nombre, ruta in (
            ('page_view', '/es/'), ('page_view', '/es/tienda/producto/1/'), ('add_to_cart', '/es/'),
        ):
            EventoAnalitica.objects.create(nombre=nombre, ruta=ruta, sesion='sx', propiedades={'ancho': 390})
        self._venta(self.ana, [(self.v_barato_s, 1)])
        self.client.force_login(self.staff)
        respuesta = self.client.get(reverse('admin_analytics'))
        self.assertContains(respuesta, 'Agregaron al carrito')
        self.assertContains(respuesta, 'Movil frente a escritorio')
        self.assertContains(respuesta, 'Stock que no rota')


class ExportacionTests(MetricasBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff = get_user_model().objects.create_user(
            email='e-staff@example.com', username='e-staff', password='x', is_staff=True,
        )

    def test_descarga_csv_con_encabezados_y_sin_datos_personales(self):
        pedido = self._venta(self.ana, [(self.v_barato_s, 2)])
        self.client.force_login(self.staff)
        respuesta = self.client.get(reverse('admin_export_orders'), {
            'desde': str(timezone.localdate()), 'hasta': str(timezone.localdate()),
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('text/csv', respuesta['Content-Type'])
        self.assertIn('attachment', respuesta['Content-Disposition'])
        texto = respuesta.content.decode('utf-8-sig')
        self.assertNotIn('@', texto)
        filas = list(csv.DictReader(io.StringIO(texto)))
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['pedido'], pedido.order_number)
        self.assertEqual(filas[0]['venta_valida'], 'si')
        self.assertEqual(filas[0]['unidades'], '2')

    def test_neutraliza_celdas_que_una_hoja_de_calculo_leeria_como_formula(self):
        self.assertEqual(_celda_segura('=HYPERLINK("x")'), "'=HYPERLINK(\"x\")")
        self.assertEqual(_celda_segura('+1'), "'+1")
        self.assertEqual(_celda_segura('@algo'), "'@algo")
        self.assertEqual(_celda_segura('PROMO10'), 'PROMO10')
        self.assertEqual(_celda_segura(12), 12)
