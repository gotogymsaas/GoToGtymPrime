"""Definiciones de las metricas de negocio (`administracion.metrics`).

Cada prueba fija una definicion: que cuenta como venta, como se compara con
el periodo anterior, como se arma el embudo. Si una definicion cambia, la
prueba que la protege tiene que cambiar a proposito."""
from datetime import date, timedelta
from decimal import Decimal

from analitica.models import EventoAnalitica
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from influencer.models import InfluencerProfile
from inventory.models import Inventory
from orders.models import Coupon, Order, OrderStatus
from orders.services import apply_order_status_transition, confirm_payment, create_order_from_cart
from payments.models import PaymentTransaction, Refund
from products.models import Brand, Product, ProductCategory, ProductVariant

from administracion import metrics

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


class _Pago:
    status = 'approved'


def _variante(producto, sku, size, stock, precio=None):
    variante = ProductVariant.objects.create(
        product=producto, sku=sku, size=size, color='negro', price_override=precio,
    )
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class MetricasBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria metricas')
        cls.otra_categoria = ProductCategory.objects.create(name='Otra categoria')
        cls.marca = Brand.objects.create(name='Marca metricas')
        cls.barato = Product.objects.create(
            name='Camiseta barata', category=cls.categoria, brand=cls.marca,
            base_price=Decimal('40000'), stock=0,
        )
        cls.caro = Product.objects.create(
            name='Chaqueta cara', category=cls.otra_categoria, brand=cls.marca,
            base_price=Decimal('400000'), stock=0,
        )
        cls.v_barato_s = _variante(cls.barato, 'MET-B-S', 'S', 500)
        cls.v_barato_m = _variante(cls.barato, 'MET-B-M', 'M', 500)
        cls.v_caro = _variante(cls.caro, 'MET-C-U', 'UNICA', 500)

        User = get_user_model()
        cls.ana = User.objects.create_user(email='m-ana@example.com', username='m-ana', password='x')
        cls.luis = User.objects.create_user(email='m-luis@example.com', username='m-luis', password='x')

    def _venta(self, usuario, lineas, *, dias_atras=0, cupon='', pagar=True):
        """Crea un pedido (y lo paga) con fecha `dias_atras` dias atras."""
        carrito = {str(variante.pk): cantidad for variante, cantidad in lineas}
        pedido = create_order_from_cart(usuario, carrito, {**DATOS, 'coupon_code': cupon})
        if pagar:
            confirm_payment(pedido, _Pago())
        if dias_atras:
            Order.objects.filter(pk=pedido.pk).update(
                created_at=timezone.now() - timedelta(days=dias_atras),
            )
        pedido.refresh_from_db()
        return pedido

    def _reembolso(self, pedido, monto, estado=Refund.Status.APPROVED):
        transaccion = PaymentTransaction.objects.create(
            order=pedido, provider='mock', status=PaymentTransaction.Status.APPROVED,
            amount=pedido.total, external_reference=pedido.order_number,
            idempotency_key=f'idem-{pedido.pk}-{monto}-{estado}',
        )
        return Refund.objects.create(payment_transaction=transaccion, amount=monto, status=estado)

    @property
    def hoy(self):
        return timezone.localdate()


class VentasTests(MetricasBase):
    def test_resumen_de_ventas_validas(self):
        a = self._venta(self.ana, [(self.v_barato_s, 2)])
        b = self._venta(self.luis, [(self.v_caro, 1)])
        resumen = metrics.resumen_ventas(self.hoy, self.hoy)

        self.assertEqual(resumen['pedidos'], 2)
        self.assertEqual(resumen['unidades'], 3)
        self.assertEqual(resumen['bruto'], Decimal('480000'))
        self.assertEqual(resumen['cobrado'], a.total + b.total)
        self.assertEqual(resumen['ticket_promedio'], (a.total + b.total) / 2)
        self.assertEqual(resumen['unidades_por_pedido'], 1.5)

    def test_un_pedido_sin_pagar_no_es_venta(self):
        self._venta(self.ana, [(self.v_barato_s, 1)], pagar=False)
        self.assertEqual(metrics.resumen_ventas(self.hoy, self.hoy)['pedidos'], 0)

    def test_un_pedido_cancelado_no_cuenta_como_ingreso_aunque_el_pago_siga_aprobado(self):
        pedido = self._venta(self.ana, [(self.v_barato_s, 1)])
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        pedido.refresh_from_db()
        # El pago sigue "aprobado": es justo lo que obliga a filtrar por estado.
        self.assertEqual(pedido.payment_status, 'approved')

        self.assertEqual(metrics.resumen_ventas(self.hoy, self.hoy)['pedidos'], 0)
        anuladas = metrics.ventas_anuladas(self.hoy, self.hoy)
        self.assertEqual(anuladas['pedidos'], 1)
        self.assertEqual(anuladas['por_devolver_pedidos'], 1)
        self.assertEqual(anuladas['por_devolver_monto'], pedido.total)

    def test_una_venta_anulada_y_reembolsada_ya_no_esta_por_devolver(self):
        pedido = self._venta(self.ana, [(self.v_barato_s, 1)])
        apply_order_status_transition(pedido, OrderStatus.CANCELLED)
        self._reembolso(pedido, pedido.total)

        anuladas = metrics.ventas_anuladas(self.hoy, self.hoy)
        self.assertEqual(anuladas['pedidos'], 1)
        self.assertEqual(anuladas['por_devolver_pedidos'], 0)
        self.assertEqual(anuladas['por_devolver_monto'], Decimal('0'))

    def test_el_reembolso_parcial_baja_el_ingreso_neto(self):
        pedido = self._venta(self.ana, [(self.v_caro, 1)])
        self._reembolso(pedido, Decimal('50000'))
        resumen = metrics.resumen_ventas(self.hoy, self.hoy)
        self.assertEqual(resumen['reembolsos'], Decimal('50000'))
        self.assertEqual(resumen['neto'], pedido.total - Decimal('50000'))

    def test_un_reembolso_pendiente_no_se_descuenta(self):
        pedido = self._venta(self.ana, [(self.v_caro, 1)])
        self._reembolso(pedido, Decimal('50000'), estado=Refund.Status.PENDING)
        self.assertEqual(metrics.resumen_ventas(self.hoy, self.hoy)['reembolsos'], Decimal('0'))

    def test_periodo_anterior_y_variacion(self):
        desde, hasta = date(2026, 10, 8), date(2026, 10, 14)  # 7 dias
        self.assertEqual(metrics.periodo_anterior(desde, hasta), (date(2026, 10, 1), date(2026, 10, 7)))
        self.assertEqual(metrics.variacion(150, 100), 50.0)
        self.assertEqual(metrics.variacion(50, 100), -50.0)
        self.assertIsNone(metrics.variacion(10, 0))

    def test_la_serie_diaria_incluye_los_dias_sin_ventas(self):
        self._venta(self.ana, [(self.v_barato_s, 1)], dias_atras=2)
        serie = metrics.serie_diaria(self.hoy - timedelta(days=3), self.hoy)
        self.assertEqual(len(serie), 4)
        self.assertEqual([f['pedidos'] for f in serie], [0, 1, 0, 0])
        self.assertEqual(serie[1]['relativo'], 100)
        self.assertEqual(serie[0]['relativo'], 0)

    def test_la_meta_es_mensual_y_se_mide_sobre_el_mes_en_curso(self):
        hoy = date(2026, 10, 10)
        pedido = self._venta(self.ana, [(self.v_caro, 1)])
        Order.objects.filter(pk=pedido.pk).update(
            created_at=timezone.make_aware(timezone.datetime(2026, 10, 5, 12, 0)),
        )
        meta = metrics.meta_del_mes(Decimal('3100000'), hoy=hoy)

        self.assertEqual(meta['acumulado'], pedido.total)
        self.assertEqual(meta['esperado_a_hoy'], Decimal('1000000'))  # 3.100.000 * 10/31
        self.assertEqual(meta['dias_restantes'], 21)
        self.assertEqual(meta['proyeccion'], pedido.total / 10 * 31)
        self.assertEqual(meta['mes_inicio'], date(2026, 10, 1))

    def test_sin_meta_no_hay_avance(self):
        self.assertIsNone(metrics.meta_del_mes(None))
        self.assertIsNone(metrics.meta_del_mes(0))

    def test_el_ranking_es_por_ingreso_y_agrupa_las_variantes_de_un_producto(self):
        self._venta(self.ana, [(self.v_barato_s, 3), (self.v_barato_m, 3)])  # 6 u x 40.000 = 240.000
        self._venta(self.luis, [(self.v_caro, 1)])                            # 1 u x 400.000
        ranking = metrics.top_productos(self.hoy, self.hoy)

        self.assertEqual([f['producto'] for f in ranking], ['Chaqueta cara', 'Camiseta barata'])
        barata = ranking[1]
        # Por unidades ganaria la camiseta (6 frente a 1); por ingreso, la chaqueta.
        self.assertEqual(barata['unidades'], 6)  # S y M en una sola fila
        self.assertEqual(barata['ingresos'], Decimal('240000'))
        self.assertAlmostEqual(ranking[0]['participacion'], 62.5, places=1)

    def test_ventas_por_categoria(self):
        self._venta(self.ana, [(self.v_barato_s, 1), (self.v_caro, 1)])
        filas = {f['categoria']: f for f in metrics.ventas_por_categoria(self.hoy, self.hoy)}
        self.assertEqual(filas['Otra categoria']['ingresos'], Decimal('400000'))
        self.assertEqual(filas['Categoria metricas']['ingresos'], Decimal('40000'))


class ClientesYCanalesTests(MetricasBase):
    def test_nuevos_frente_a_recurrentes(self):
        self._venta(self.ana, [(self.v_barato_s, 1)], dias_atras=60)  # compro antes del rango
        self._venta(self.ana, [(self.v_barato_s, 1)])                  # vuelve en el rango
        self._venta(self.luis, [(self.v_barato_s, 1)])                 # primera compra en el rango
        self._venta(self.luis, [(self.v_barato_m, 1)])                 # y repite en el rango
        resultado = metrics.clientes(self.hoy - timedelta(days=30), self.hoy)

        self.assertEqual(resultado['compradores'], 2)
        self.assertEqual(resultado['nuevos'], 1)
        self.assertEqual(resultado['recurrentes'], 1)
        self.assertEqual(resultado['repiten_en_el_rango'], 1)
        self.assertEqual(resultado['tasa_recurrentes'], 50.0)

    def test_los_pedidos_anulados_no_hacen_recurrente_a_nadie(self):
        anulado = self._venta(self.ana, [(self.v_barato_s, 1)], dias_atras=60)
        apply_order_status_transition(anulado, OrderStatus.CANCELLED)
        self._venta(self.ana, [(self.v_barato_s, 1)])
        resultado = metrics.clientes(self.hoy - timedelta(days=30), self.hoy)
        self.assertEqual(resultado['nuevos'], 1)
        self.assertEqual(resultado['recurrentes'], 0)

    def test_el_cupon_queda_guardado_en_el_pedido(self):
        cupon = Coupon.objects.create(code='PROMO10', discount_type='percentage', value=10)
        pedido = self._venta(self.ana, [(self.v_caro, 1)], cupon='promo10')
        self.assertEqual(pedido.coupon, cupon)
        sin_cupon = self._venta(self.luis, [(self.v_caro, 1)])
        self.assertIsNone(sin_cupon.coupon)

    def test_rendimiento_de_cupones(self):
        Coupon.objects.create(code='PROMO10', discount_type='percentage', value=10)
        self._venta(self.ana, [(self.v_caro, 1)], cupon='PROMO10')
        self._venta(self.luis, [(self.v_caro, 1)], cupon='PROMO10')
        self._venta(self.luis, [(self.v_caro, 1)])  # sin cupon: no aparece
        filas = metrics.rendimiento_de_cupones(self.hoy, self.hoy)

        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['codigo'], 'PROMO10')
        self.assertEqual(filas[0]['pedidos'], 2)
        self.assertEqual(filas[0]['descuento'], Decimal('80000'))

    def test_origen_de_la_venta(self):
        perfil = InfluencerProfile.objects.create(user=self.luis)
        Coupon.objects.create(code='AFIL1', discount_type='percentage', value=10, influencer=perfil)
        Coupon.objects.create(code='GENERAL', discount_type='percentage', value=5)
        self._venta(self.ana, [(self.v_caro, 1)], cupon='AFIL1')
        self._venta(self.ana, [(self.v_caro, 1)], cupon='GENERAL')
        self._venta(self.ana, [(self.v_caro, 1)])
        filas = {f['canal']: f for f in metrics.canales_de_venta(self.hoy, self.hoy)}

        self.assertEqual(filas['Con cupon de afiliado']['pedidos'], 1)
        self.assertEqual(filas['Con otro cupon']['pedidos'], 1)
        self.assertEqual(filas['Sin descuento']['pedidos'], 1)
        self.assertAlmostEqual(
            sum(f['participacion'] for f in filas.values()), 100.0, delta=0.2,
        )


class EmbudoTests(TestCase):
    def _evento(self, sesion, nombre, ruta='/es/', **propiedades):
        return EventoAnalitica.objects.create(
            nombre=nombre, ruta=ruta, sesion=sesion, propiedades=propiedades,
        )

    def _hoy(self):
        return timezone.localdate()

    def setUp(self):
        # s1 compra; s2 abandona el carrito; s3 solo ve la portada; s4 ve un producto.
        for sesion, ancho in (('s1', 1440), ('s2', 390), ('s3', 390), ('s4', 1440)):
            self._evento(sesion, 'page_view', ancho=ancho)
        for sesion in ('s1', 's2', 's4'):
            self._evento(sesion, 'page_view', '/es/tienda/producto/3/', ancho=1440)
        for sesion in ('s1', 's2'):
            self._evento(sesion, 'add_to_cart')
        self._evento('s1', 'page_view', '/es/pedidos-tienda/checkout/')
        self._evento('s1', 'order_created', '/es/pedidos-tienda/checkout/', valor=100000)

    def test_cada_etapa_exige_haber_pasado_la_anterior(self):
        # Una sesion que agrega al carrito sin haber visto un producto no
        # cuenta como "agrego al carrito": el embudo es acumulado.
        self._evento('s9', 'page_view')
        self._evento('s9', 'add_to_cart')
        resultado = metrics.embudo(self._hoy(), self._hoy())
        cantidades = [f['sesiones'] for f in resultado['etapas']]
        self.assertEqual(cantidades, [5, 3, 2, 1, 1])

    def test_proporciones_entre_etapas(self):
        filas = {f['clave']: f for f in metrics.embudo(self._hoy(), self._hoy())['etapas']}
        self.assertEqual(filas['sesiones']['del_inicio'], 100.0)
        self.assertEqual(filas['producto']['del_inicio'], 75.0)
        self.assertAlmostEqual(filas['carrito']['del_paso_anterior'], 66.7, places=1)
        self.assertEqual(filas['pedido']['del_paso_anterior'], 100.0)

    def test_el_embudo_se_parte_por_dispositivo_segun_la_primera_vista(self):
        resultado = metrics.embudo(self._hoy(), self._hoy())
        movil = {f['clave']: f['sesiones'] for f in resultado['por_dispositivo']['movil']}
        escritorio = {f['clave']: f['sesiones'] for f in resultado['por_dispositivo']['escritorio']}
        self.assertEqual((movil['sesiones'], movil['carrito'], movil['pedido']), (2, 1, 0))
        self.assertEqual((escritorio['sesiones'], escritorio['carrito'], escritorio['pedido']), (2, 1, 1))

    def test_sin_eventos_no_hay_datos(self):
        EventoAnalitica.objects.all().delete()
        resultado = metrics.embudo(self._hoy(), self._hoy())
        self.assertFalse(resultado['hay_datos'])
        self.assertEqual([f['sesiones'] for f in resultado['etapas']], [0, 0, 0, 0, 0])

    def test_solo_cuenta_eventos_del_rango(self):
        resultado = metrics.embudo(date(2000, 1, 1), date(2000, 1, 2))
        self.assertFalse(resultado['hay_datos'])

    def test_canales_de_trafico_por_origen_de_la_primera_vista(self):
        EventoAnalitica.objects.all().delete()
        self._evento('a', 'page_view', utm_source='instagram', utm_medium='bio')
        self._evento('b', 'page_view', ref='ANA123')
        self._evento('c', 'page_view', referrer='google.com')
        self._evento('d', 'page_view')
        self._evento('d', 'page_view', utm_source='tarde')  # origen que aparece despues
        self._evento('a', 'page_view', '/es/tienda/producto/3/')
        self._evento('a', 'add_to_cart')
        canales = {f['canal']: f for f in metrics.canales_de_trafico(self._hoy(), self._hoy())}

        self.assertEqual(canales['instagram / bio']['sesiones'], 1)
        self.assertEqual(canales['instagram / bio']['carritos'], 1)
        self.assertEqual(canales['Afiliado: ANA123']['sesiones'], 1)
        self.assertEqual(canales['google.com']['sesiones'], 1)
        self.assertEqual(canales['tarde']['sesiones'], 1)

    def test_busquedas_y_demanda_sin_atender(self):
        categoria = ProductCategory.objects.create(name='C busq')
        marca = Brand.objects.create(name='M busq')
        Product.objects.create(
            name='Zzleggins negro', category=categoria, brand=marca, base_price=Decimal('1'), stock=0,
        )
        for termino in ('Zzleggins', 'zzleggins ', 'zapatillas', 'zapatillas', 'zapatillas'):
            self._evento('x', 'search_submit', termino=termino)
        self._evento('x', 'search_submit', termino='', vacia=1)
        resultado = metrics.busquedas(self._hoy(), self._hoy())

        self.assertEqual(resultado['total'], 6)
        self.assertEqual(resultado['sin_termino'], 1)
        terminos = {f['termino']: f for f in resultado['terminos']}
        self.assertEqual(terminos['zzleggins']['veces'], 2)
        self.assertEqual(terminos['zzleggins']['resultados'], 1)
        self.assertEqual([f['termino'] for f in resultado['sin_resultados']], ['zapatillas'])


class OperacionEInventarioTests(MetricasBase):
    def test_pedidos_sin_pagar_por_mas_de_24_horas(self):
        self._venta(self.ana, [(self.v_barato_s, 1)], pagar=False, dias_atras=2)
        self._venta(self.ana, [(self.v_barato_s, 1)], pagar=False)  # reciente
        resultado = metrics.pipeline_de_pedidos(self.hoy - timedelta(days=5), self.hoy)
        self.assertEqual(resultado['sin_pagar_24h'], 1)
        self.assertEqual(resultado['creados'], 2)

    def test_tasas_de_cancelacion_y_devolucion(self):
        for _ in range(3):
            self._venta(self.ana, [(self.v_barato_s, 1)])
        cancelado = self._venta(self.ana, [(self.v_barato_s, 1)])
        apply_order_status_transition(cancelado, OrderStatus.CANCELLED)
        resultado = metrics.pipeline_de_pedidos(self.hoy, self.hoy)
        self.assertEqual(resultado['tasa_cancelacion'], 25.0)
        self.assertEqual(resultado['tasa_devolucion'], 0.0)
        etiquetas = {f['estado']: f['pedidos'] for f in resultado['estados']}
        self.assertEqual(etiquetas['Cancelado'], 1)

    def test_cobertura_riesgo_y_stock_sin_rotacion(self):
        riesgo = _variante(self.barato, 'MET-B-L', 'L', 5)
        agotada = _variante(self.barato, 'MET-B-XL', 'XL', 3)
        # `riesgo`: vende 30 en 30 dias (1 al dia) con 5 en stock = 5 dias de cobertura.
        self._venta(self.ana, [(self.v_barato_s, 1)])  # mantiene S con venta, 499 en stock
        Inventory.objects.filter(variant=riesgo).update(quantity_available=35)
        self._venta(self.ana, [(riesgo, 30)])
        # `agotada`: se vende todo el stock.
        self._venta(self.ana, [(agotada, 3)])

        resultado = metrics.salud_de_inventario()
        en_riesgo = {f['sku']: f for f in resultado['en_riesgo']}
        self.assertEqual(en_riesgo['MET-B-L']['cobertura_dias'], 5)
        self.assertEqual(en_riesgo['MET-B-XL']['cobertura_dias'], 0)
        self.assertNotIn('MET-B-S', en_riesgo)  # mucho stock para su ritmo

        # La chaqueta nunca se vendio: su stock no rota.
        sin_rotacion = {f['sku'] for f in resultado['sin_rotacion']}
        self.assertIn('MET-C-U', sin_rotacion)
        self.assertNotIn('MET-B-L', sin_rotacion)
        self.assertEqual(
            next(f['valor'] for f in resultado['sin_rotacion'] if f['sku'] == 'MET-C-U'),
            Decimal('500') * Decimal('400000'),
        )
        self.assertGreater(resultado['valor_sin_rotacion'], 0)

    def test_exportacion_sin_datos_personales_y_con_bandera_de_venta_valida(self):
        valido = self._venta(self.ana, [(self.v_barato_s, 2)])
        anulado = self._venta(self.luis, [(self.v_barato_m, 1)])
        apply_order_status_transition(anulado, OrderStatus.CANCELLED)
        pendiente = self._venta(self.luis, [(self.v_barato_m, 1)], pagar=False)

        filas = {f['pedido']: f for f in metrics.filas_exportacion(self.hoy, self.hoy)}
        self.assertEqual(filas[valido.order_number]['venta_valida'], 'si')
        self.assertEqual(filas[valido.order_number]['unidades'], 2)
        self.assertEqual(filas[anulado.order_number]['venta_valida'], 'no')
        self.assertEqual(filas[pendiente.order_number]['venta_valida'], 'no')
        self.assertEqual(set(filas[valido.order_number]), set(metrics.COLUMNAS_EXPORTACION))
        volcado = ' '.join(str(v) for fila in filas.values() for v in fila.values())
        self.assertNotIn('@', volcado)
