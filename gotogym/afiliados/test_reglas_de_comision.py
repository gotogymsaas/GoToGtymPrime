"""Reglas de comision: autocompra, periodo de validacion, reembolsos,
recuperacion de lo ya pagado y anulacion manual."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO

from django.apps import apps
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from orders.models import Order, OrderStatus
from orders.services import apply_order_status_transition, confirm_payment, create_order_from_cart

from .models import Commission, CommissionStatus, PerfilAfiliado, WithdrawalStatus
from .services import (
    anular_comision,
    confirmar_comisiones_vencidas,
    extender_validacion,
    fin_de_validacion,
    liberar_revision,
    pedidos_validos,
    request_withdrawal,
    resolve_withdrawal,
)
from .tests import DATOS_ENTREGA, AfiliadoTestBase, _FakeTransaction


def _modelo_de_pagos(nombre):
    """`payments` es una app hermana de `afiliados`: sus modelos se piden por
    nombre para no importarla (los reembolsos son lo unico que las pruebas
    necesitan de ella)."""
    return apps.get_model('payments', nombre)


class _ConPedidos(AfiliadoTestBase):
    def _pedido_con_datos(self, perfil, **datos):
        cupon = perfil.coupons.first()
        entrega = dict(DATOS_ENTREGA, coupon_code=cupon.code, **datos)
        pedido = create_order_from_cart(self.comprador, {str(self.variante.pk): 1}, entrega)
        confirm_payment(pedido, _FakeTransaction('approved'))
        return pedido

    def _aprobar_pago_real(self, pedido):
        """Una transaccion aprobada de verdad, para poder reembolsarla."""
        return _modelo_de_pagos('PaymentTransaction').objects.create(
            order=pedido, provider='mock', payment_id=f'mock-{pedido.pk}', external_reference=pedido.order_number,
            status='approved', amount=pedido.total, idempotency_key=f'idem-{pedido.pk}',
        )

    def _en_el_futuro(self, dias=60):
        return timezone.now() + timedelta(days=dias)


class AutocompraTests(_ConPedidos):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.perfil.phone = '300 555 1234'
        self.perfil.address = 'Carrera 7 # 45-67, Bogota'
        self.perfil.save(update_fields=['phone', 'address'])

    def test_una_compra_ajena_no_se_marca(self):
        comision = Commission.objects.get(order=self._pedido_con_datos(self.perfil))
        self.assertFalse(comision.needs_review)

    def test_el_correo_del_afiliado_marca_la_comision_para_revision(self):
        pedido = self._pedido_con_datos(self.perfil, email=self.afiliado_user.email.upper())
        comision = Commission.objects.get(order=pedido)
        self.assertTrue(comision.needs_review)
        self.assertIn('correo', comision.review_reason)

    def test_el_telefono_del_afiliado_marca_la_comision_aunque_este_escrito_distinto(self):
        pedido = self._pedido_con_datos(self.perfil, phone='+57 (300) 555-1234')
        comision = Commission.objects.get(order=pedido)
        self.assertTrue(comision.needs_review)
        self.assertIn('teléfono', comision.review_reason)

    def test_la_direccion_del_afiliado_marca_la_comision(self):
        pedido = self._pedido_con_datos(self.perfil, address_line='carrera 7 # 45-67')
        comision = Commission.objects.get(order=pedido)
        self.assertTrue(comision.needs_review)
        self.assertIn('dirección', comision.review_reason)

    def test_una_comision_en_revision_no_se_confirma_hasta_liberarla(self):
        pedido = self._pedido_con_datos(self.perfil, email=self.afiliado_user.email)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        comision = Commission.objects.get(order=pedido)

        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.PENDING)

        liberar_revision(comision, self.admin, 'Es otra persona.')
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.APPROVED)
        self.assertFalse(comision.needs_review)


class PeriodoDeValidacionTests(_ConPedidos):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()

    def test_hasta_que_el_pedido_se_entrega_no_hay_fecha_de_validacion(self):
        pedido = self._pedido_con_datos(self.perfil)
        comision = Commission.objects.get(order=pedido)
        self.assertIsNone(comision.validation_ends_at)
        self.assertIsNone(comision.validation_last_day)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro(365))
        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.PENDING)

    def test_al_entregarse_se_fija_el_fin_de_la_validacion(self):
        pedido = self._pedido_con_datos(self.perfil)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        pedido.refresh_from_db()
        self.assertIsNotNone(pedido.delivered_at)
        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.validation_ends_at, fin_de_validacion(pedido.delivered_at))

    def test_cinco_dias_habiles_se_saltan_fines_de_semana_y_festivos(self):
        # Entregado el jueves 8 de octubre de 2026: el lunes 12 es festivo, asi
        # que el quinto dia habil es el viernes 16 y se confirma el sabado 17.
        entregado = timezone.make_aware(datetime(2026, 10, 8, 15, 0))
        fin = timezone.localtime(fin_de_validacion(entregado))
        self.assertEqual(fin.date(), date(2026, 10, 17))
        self.assertEqual((fin.hour, fin.minute), (0, 0))

    def test_no_se_confirma_antes_del_plazo_y_si_despues(self):
        pedido = self._pedido_con_datos(self.perfil)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        comision = Commission.objects.get(order=pedido)

        self.assertEqual(confirmar_comisiones_vencidas(ahora=comision.validation_ends_at - timedelta(minutes=1)), 0)
        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.PENDING)

        self.assertEqual(confirmar_comisiones_vencidas(ahora=comision.validation_ends_at), 1)
        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.APPROVED)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.commission_balance, comision.amount)

    def test_confirmar_es_idempotente(self):
        self._pedido_entregado(self.perfil)
        self.assertEqual(confirmar_comisiones_vencidas(ahora=self._en_el_futuro()), 0)

    def test_una_comision_de_un_pedido_ya_entregado_sin_fecha_se_completa(self):
        """Pedidos entregados cuando aun no se guardaba el plazo."""
        pedido = self._pedido_con_datos(self.perfil)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        Commission.objects.filter(order=pedido).update(validation_ends_at=None)

        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())

        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.APPROVED)

    def test_la_extension_desplaza_la_fecha_y_avisa_al_afiliado(self):
        pedido = self._pedido_con_datos(self.perfil)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        comision = Commission.objects.get(order=pedido)
        hasta = timezone.localdate() + timedelta(days=40)

        with self.captureOnCommitCallbacks(execute=True):
            extender_validacion(comision, hasta, 'Reclamo por posible fraude', self.admin)

        comision.refresh_from_db()
        self.assertEqual(comision.validation_last_day, hasta)
        confirmar_comisiones_vencidas(ahora=timezone.now() + timedelta(days=30))
        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.PENDING)
        confirmar_comisiones_vencidas(ahora=timezone.now() + timedelta(days=41))
        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.APPROVED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Reclamo por posible fraude', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.afiliado_user.email])

    def test_la_extension_exige_motivo_fecha_posterior_y_comision_pendiente(self):
        pedido = self._pedido_con_datos(self.perfil)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        comision = Commission.objects.get(order=pedido)
        with self.assertRaises(ValueError):
            extender_validacion(comision, timezone.localdate() + timedelta(days=30), ' ', self.admin)
        with self.assertRaises(ValueError):
            extender_validacion(comision, timezone.localdate(), 'Motivo', self.admin)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        comision.refresh_from_db()
        with self.assertRaises(ValueError):
            extender_validacion(comision, timezone.localdate() + timedelta(days=90), 'Motivo', self.admin)

    def test_una_devolucion_durante_la_validacion_revierte_la_comision(self):
        pedido = self._pedido_con_datos(self.perfil)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        apply_order_status_transition(pedido, OrderStatus.RETURNED)
        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.REVERTED)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.REVERTED)

    def test_las_comisiones_se_muestran_como_confirmadas(self):
        self.assertEqual(CommissionStatus.APPROVED.label, 'Confirmada')
        self.assertEqual(CommissionStatus.APPROVED.value, 'approved')

    def test_el_panel_dice_hasta_cuando_se_valida(self):
        pedido = self._pedido_con_datos(self.perfil)
        self.client.force_login(self.afiliado_user)
        self.assertContains(self.client.get(reverse('afiliado_compras_referidas')), '5 días hábiles después de la entrega')
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        comision = Commission.objects.get(order=pedido)
        self.assertContains(
            self.client.get(reverse('afiliado_compras_referidas')),
            f'En validación hasta el {comision.validation_last_day:%d/%m/%Y}',
        )

    def test_el_comando_confirma_las_comisiones_vencidas(self):
        pedido = self._pedido_con_datos(self.perfil)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        Commission.objects.filter(order=pedido).update(validation_ends_at=timezone.now() - timedelta(days=1))

        call_command('confirmar_comisiones', stdout=StringIO())

        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.APPROVED)

    def test_abrir_el_panel_confirma_lo_vencido_sin_tarea_programada(self):
        pedido = self._pedido_con_datos(self.perfil)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        Commission.objects.filter(order=pedido).update(validation_ends_at=timezone.now() - timedelta(days=1))
        self.client.force_login(self.afiliado_user)

        self.client.get(reverse('afiliado_dashboard'))

        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.APPROVED)


class ReembolsosYRecuperacionTests(_ConPedidos):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)

    def _reembolsar(self, pedido):
        return self.client.post(reverse('admin_order_refund', args=[pedido.order_number]))

    def test_reembolsar_un_pedido_anula_su_comision(self):
        pedido = self._pedido_con_datos(self.perfil)
        self._aprobar_pago_real(pedido)

        self._reembolsar(pedido)

        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.status, CommissionStatus.REVERTED)
        self.assertIn('reembolsado', comision.adjustment_reason)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.commission_balance, Decimal('0.00'))
        self.assertEqual(self.perfil.total_referred, 0)
        self.assertEqual(self.perfil.total_sales, Decimal('0.00'))

    def test_una_comision_reembolsada_no_se_confirma_aunque_se_entregue(self):
        pedido = self._pedido_con_datos(self.perfil)
        self._aprobar_pago_real(pedido)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        comision = Commission.objects.get(order=pedido)
        # Reembolso que llega sin pasar por la anulacion de la vista.
        _modelo_de_pagos('Refund').objects.create(
            payment_transaction=pedido.payment_transactions.first(), amount=pedido.total, status='approved',
        )

        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())

        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.REVERTED)

    def test_lo_ya_pagado_de_un_pedido_reembolsado_queda_por_recuperar(self):
        pedido = self._pedido_con_datos(self.perfil)
        self._aprobar_pago_real(pedido)
        apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        resolve_withdrawal(request_withdrawal(self.perfil), True, self.admin)
        comision = Commission.objects.get(order=pedido)
        self.assertEqual(comision.status, CommissionStatus.PAID)

        self._reembolsar(pedido)

        comision.refresh_from_db()
        self.assertEqual(comision.status, CommissionStatus.CLAWBACK)

    def test_lo_por_recuperar_se_descuenta_del_siguiente_pago(self):
        primero = self._pedido_con_datos(self.perfil)
        self._aprobar_pago_real(primero)
        apply_order_status_transition(primero, OrderStatus.DELIVERED)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        resolve_withdrawal(request_withdrawal(self.perfil), True, self.admin)
        self._reembolsar(primero)
        primera = Commission.objects.get(order=primero)

        # Con solo lo por recuperar no hay nada que pagar.
        self.assertIsNone(request_withdrawal(self.perfil))
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.commission_balance, Decimal('0.00'))

        # Dos ventas nuevas: la solicitud paga la suma menos lo recuperado.
        nuevos = [self._pedido_con_datos(self.perfil) for _ in range(2)]
        for pedido in nuevos:
            apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        confirmadas = sum(Commission.objects.get(order=p).amount for p in nuevos)

        solicitud = request_withdrawal(self.perfil)

        self.assertEqual(solicitud.recovery_amount, primera.amount)
        self.assertEqual(solicitud.amount, confirmadas - primera.amount)
        resolve_withdrawal(solicitud, True, self.admin)
        primera.refresh_from_db()
        self.assertEqual(primera.status, CommissionStatus.REVERTED)
        self.assertEqual(solicitud.net_paid, solicitud.amount)

    def test_rechazar_la_solicitud_suelta_tambien_lo_por_recuperar(self):
        primero = self._pedido_con_datos(self.perfil)
        self._aprobar_pago_real(primero)
        apply_order_status_transition(primero, OrderStatus.DELIVERED)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        resolve_withdrawal(request_withdrawal(self.perfil), True, self.admin)
        self._reembolsar(primero)
        for _ in range(2):
            apply_order_status_transition(self._pedido_con_datos(self.perfil), OrderStatus.DELIVERED)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        solicitud = request_withdrawal(self.perfil)

        resolve_withdrawal(solicitud, False, self.admin)

        self.assertEqual(Commission.objects.get(order=primero).status, CommissionStatus.CLAWBACK)
        self.assertIsNone(Commission.objects.get(order=primero).recovered_in)

    def test_anular_una_comision_ya_solicitada_ajusta_la_solicitud(self):
        pedidos = [self._pedido_con_datos(self.perfil) for _ in range(2)]
        for pedido in pedidos:
            apply_order_status_transition(pedido, OrderStatus.DELIVERED)
        confirmar_comisiones_vencidas(ahora=self._en_el_futuro())
        solicitud = request_withdrawal(self.perfil)
        total = solicitud.amount
        a_anular = Commission.objects.get(order=pedidos[0])

        anular_comision(a_anular, 'Fraude', self.admin)

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.amount, total - a_anular.amount)
        self.assertEqual(solicitud.status, WithdrawalStatus.PENDING)

    def test_si_se_anula_todo_lo_solicitado_la_solicitud_se_rechaza(self):
        pedido = self._pedido_entregado(self.perfil)
        solicitud = request_withdrawal(self.perfil)

        anular_comision(Commission.objects.get(order=pedido), 'Fraude', self.admin)

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.status, WithdrawalStatus.REJECTED)

    def test_los_pedidos_cancelados_devueltos_o_reembolsados_no_cuentan_como_ventas(self):
        entregado = self._pedido_con_datos(self.perfil)
        cancelado = self._pedido_con_datos(self.perfil)
        reembolsado = self._pedido_con_datos(self.perfil)
        self._aprobar_pago_real(reembolsado)
        apply_order_status_transition(cancelado, OrderStatus.CANCELLED)
        self._reembolsar(reembolsado)

        validos = list(pedidos_validos(self.perfil))

        self.assertEqual(validos, [Order.objects.get(pk=entregado.pk)])
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.total_referred, 1)
        self.assertEqual(self.perfil.total_sales, entregado.subtotal)


class AnulacionManualTests(_ConPedidos):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.pedido = self._pedido_con_datos(self.perfil)
        self.comision = Commission.objects.get(order=self.pedido)
        self.url = reverse('admin_commission_void', args=[self.comision.pk])

    def test_exige_motivo(self):
        with self.assertRaises(ValueError):
            anular_comision(self.comision, '   ', self.admin)

    def test_el_admin_anula_con_motivo_y_queda_constancia(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)

        self.client.post(self.url, {'reason': 'Error de seguimiento'})

        self.comision.refresh_from_db()
        self.assertEqual(self.comision.status, CommissionStatus.REVERTED)
        self.assertEqual(self.comision.adjustment_reason, 'Error de seguimiento')
        self.assertEqual(self.comision.adjusted_by, self.admin)
        self.assertIsNotNone(self.comision.adjusted_at)

    def test_sin_motivo_la_vista_no_anula(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)

        respuesta = self.client.post(self.url, {'reason': ''}, follow=True)

        self.comision.refresh_from_db()
        self.assertEqual(self.comision.status, CommissionStatus.PENDING)
        self.assertContains(respuesta, 'motivo de la anulación')

    def test_sin_el_permiso_no_se_puede_anular(self):
        from django.contrib.auth.models import Group

        # Un staff con grupo es un rol intermedio: no recibe el paquete completo.
        self.admin.groups.add(Group.objects.create(name='Grupo sin permiso de comisiones'))
        self.client.force_login(self.admin)
        self.client.post(self.url, {'reason': 'X'})
        self.comision.refresh_from_db()
        self.assertEqual(self.comision.status, CommissionStatus.PENDING)

    def test_el_detalle_del_admin_muestra_base_tasa_y_acciones(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        html = self.client.get(reverse('admin_afiliado_detail', args=[self.perfil.pk])).content.decode()
        self.assertIn(self.pedido.order_number, html)
        self.assertIn('20,00%', html)
        self.assertIn(reverse('admin_commission_void', args=[self.comision.pk]), html)
        self.assertIn(reverse('admin_commission_extend', args=[self.comision.pk]), html)

    def test_el_admin_extiende_desde_la_vista(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        apply_order_status_transition(self.pedido, OrderStatus.DELIVERED)
        hasta = (timezone.localdate() + timedelta(days=30)).isoformat()

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('admin_commission_extend', args=[self.comision.pk]),
                {'until': hasta, 'reason': 'Revisión de fraude'},
            )

        self.comision.refresh_from_db()
        self.assertEqual(self.comision.extension_reason, 'Revisión de fraude')
        self.assertEqual(len(mail.outbox), 1)

    def test_el_admin_libera_una_comision_en_revision(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        Commission.objects.filter(pk=self.comision.pk).update(needs_review=True, review_reason='Parece autocompra')

        self.client.post(reverse('admin_commission_release', args=[self.comision.pk]), {'note': 'Verificado'})

        self.comision.refresh_from_db()
        self.assertFalse(self.comision.needs_review)
        self.assertEqual(self.comision.adjusted_by, self.admin)

    def test_el_listado_avisa_de_las_comisiones_en_revision(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        Commission.objects.filter(pk=self.comision.pk).update(needs_review=True)
        self.assertContains(self.client.get(reverse('admin_afiliados')), 'marcada para revisión')


class PedidosDemoradosTests(_ConPedidos):
    def test_el_filtro_lista_los_enviados_hace_mas_de_diez_dias(self):
        perfil = self._crear_perfil_aprobado()
        demorado = self._pedido_con_datos(perfil)
        reciente = self._pedido_con_datos(perfil)
        for pedido in (demorado, reciente):
            apply_order_status_transition(pedido, OrderStatus.SHIPPED)
        Order.objects.filter(pk=demorado.pk).update(updated_at=timezone.now() - timedelta(days=11))
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse('admin_orders'), {'demorados': '1'})

        numeros = [orden.order_number for orden in respuesta.context['page_obj']]
        self.assertEqual(numeros, [demorado.order_number])
        self.assertContains(respuesta, 'siguen sin marcarse como entregados')


class PerfilesSinComisionTests(AfiliadoTestBase):
    def test_un_perfil_nuevo_tiene_tasa_global_de_20(self):
        PerfilAfiliado.objects.create(user=self.afiliado_user)
        from .models import ConfiguracionProgramaAfiliados
        ConfiguracionProgramaAfiliados.objects.all().delete()
        self.assertEqual(ConfiguracionProgramaAfiliados.load().default_commission_rate, Decimal('20.00'))
        self.assertEqual(ConfiguracionProgramaAfiliados.load().minimum_payout, Decimal('100000.00'))
