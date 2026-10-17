"""Pagos: minimo, fecha limite, gastos de transaccion, total pagado por ano,
titularidad de la cuenta y cobro de quien ya salio del programa."""
import importlib
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.apps import apps as django_apps
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from .models import (
    Commission,
    CommissionStatus,
    ConfiguracionProgramaAfiliados,
    EstadoAfiliado,
    PayoutAccount,
    PerfilAfiliado,
    WithdrawalRequest,
    WithdrawalStatus,
)
from .services import (
    MontoMinimoError,
    confirmar_comisiones_vencidas,
    deactivate_afiliado,
    fecha_limite_de_pago,
    request_withdrawal,
    resolve_withdrawal,
    total_pagado_en_anio,
    totales_pagados_por_anio,
)
from .terminos import COMISION_GLOBAL_EN_TERMINOS
from .tests import AfiliadoTestBase


def _mensajes(respuesta):
    from django.contrib.messages import get_messages
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


def _pagada(perfil, monto, resuelta, gastos='0'):
    return WithdrawalRequest.objects.create(
        afiliado=perfil, amount=Decimal(monto), transaction_fee=Decimal(gastos),
        status=WithdrawalStatus.PAID, resolved_at=resuelta,
    )


class MinimoDePagoTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self._inscribir_cuenta(self.perfil)
        self.pedido = self._pedido_entregado(self.perfil)
        self.comision = Commission.objects.get(order=self.pedido)

    def _fijar_minimo(self, valor):
        ConfiguracionProgramaAfiliados.objects.filter(pk=1).update(minimum_payout=valor)

    def test_bajo_el_minimo_no_se_crea_la_solicitud(self):
        self._fijar_minimo(self.comision.amount + 1)
        with self.assertRaises(MontoMinimoError) as contexto:
            request_withdrawal(self.perfil)
        self.assertEqual(contexto.exception.disponible, self.comision.amount)
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_en_el_minimo_exacto_si_se_crea(self):
        self._fijar_minimo(self.comision.amount)
        self.assertEqual(request_withdrawal(self.perfil).amount, self.comision.amount)

    def test_la_vista_explica_cuanto_falta(self):
        self._fijar_minimo(self.comision.amount + 5000)
        self.client.force_login(self.afiliado_user)

        respuesta = self.client.post(reverse('afiliado_solicitar_retiro'))

        self.assertIn('Necesitas al menos', _mensajes(respuesta)[-1])
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_el_panel_oculta_el_boton_y_dice_cuanto_falta(self):
        self._fijar_minimo(self.comision.amount + 5000)
        self.client.force_login(self.afiliado_user)
        html = self.client.get(reverse('afiliado_dashboard')).content.decode()
        self.assertNotIn('Solicitar comisión</summary>', html)
        self.assertIn('Te faltan $5.000 COP', html)

    def test_lo_pendiente_no_cuenta_para_el_minimo(self):
        self._fijar_minimo(self.comision.amount + 1)
        otro = self._pedido_entregado_en_validacion(self.perfil)
        self.assertEqual(Commission.objects.get(order=otro).status, CommissionStatus.PENDING)
        with self.assertRaises(MontoMinimoError):
            request_withdrawal(self.perfil)


class FechaLimiteDePagoTests(AfiliadoTestBase):
    def test_se_paga_en_los_primeros_diez_dias_habiles_del_mes_siguiente(self):
        self.assertEqual(fecha_limite_de_pago(date(2026, 10, 15)), date(2026, 11, 17))
        self.assertEqual(fecha_limite_de_pago(date(2026, 1, 31)), date(2026, 2, 13))

    def test_diciembre_pasa_a_enero(self):
        self.assertEqual(fecha_limite_de_pago(date(2026, 12, 20)), date(2027, 1, 18))  # el 1 y el 11 de enero son festivos

    def test_el_panel_muestra_la_fecha_limite_de_la_solicitud_en_curso(self):
        perfil = self._crear_perfil_aprobado()
        self._inscribir_cuenta(perfil)
        self._pedido_entregado(perfil)
        solicitud = request_withdrawal(perfil)
        self.client.force_login(self.afiliado_user)

        html = self.client.get(reverse('afiliado_dashboard')).content.decode()

        limite = fecha_limite_de_pago(timezone.localtime(solicitud.requested_at).date())
        self.assertIn(f'a más tardar el {limite:%d/%m/%Y}', html)

    def test_el_admin_ve_hasta_cuando_pagar(self):
        perfil = self._crear_perfil_aprobado()
        self._pedido_entregado(perfil)
        solicitud = request_withdrawal(perfil)
        self.client.force_login(self.admin)
        limite = fecha_limite_de_pago(timezone.localtime(solicitud.requested_at).date())
        self.assertContains(self.client.get(reverse('admin_afiliados')), f'{limite:%d/%m/%Y}')


class GastosDeTransaccionTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self._pedido_entregado(self.perfil)
        self.solicitud = request_withdrawal(self.perfil)

    def test_los_gastos_se_descuentan_de_lo_que_recibe(self):
        resolve_withdrawal(self.solicitud, True, self.admin, transaction_fee=Decimal('1500'))
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.transaction_fee, Decimal('1500.00'))
        self.assertEqual(self.solicitud.net_paid, self.solicitud.amount - Decimal('1500.00'))

    def test_sin_gastos_recibe_todo(self):
        resolve_withdrawal(self.solicitud, True, self.admin)
        self.assertEqual(self.solicitud.net_paid, self.solicitud.amount)

    def test_los_gastos_no_pueden_ser_negativos_ni_mayores_al_monto(self):
        for gastos in (Decimal('-1'), self.solicitud.amount + 1):
            with self.subTest(gastos=gastos), self.assertRaises(ValueError):
                resolve_withdrawal(self.solicitud, True, self.admin, transaction_fee=gastos)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.status, WithdrawalStatus.PENDING)

    def test_el_admin_registra_los_gastos_al_pagar(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('admin_withdrawal_resolve', args=[self.solicitud.pk]),
                {'action': 'pay', 'transaction_fee': '2000'},
            )
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.transaction_fee, Decimal('2000.00'))
        self.assertIn('Gastos de transacción: $2.000 COP', mail.outbox[0].body)
        self.assertIn('Total recibido', mail.outbox[0].body)

    def test_un_valor_de_gastos_invalido_no_paga(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('admin_withdrawal_resolve', args=[self.solicitud.pk]),
            {'action': 'pay', 'transaction_fee': 'abc'},
        )
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.status, WithdrawalStatus.PENDING)
        self.assertIn('gastos de transacción', _mensajes(respuesta)[-1])


class TotalPagadoPorAnioTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        tz = timezone.get_current_timezone()
        _pagada(self.perfil, '100000', datetime(2025, 3, 10, 12, tzinfo=tz))
        _pagada(self.perfil, '200000', datetime(2026, 2, 5, 12, tzinfo=tz), gastos='1000')
        _pagada(self.perfil, '50000', datetime(2026, 8, 20, 12, tzinfo=tz))
        WithdrawalRequest.objects.create(
            afiliado=self.perfil, amount=Decimal('999999'), status=WithdrawalStatus.REJECTED,
            resolved_at=datetime(2026, 5, 1, tzinfo=tz),
        )
        WithdrawalRequest.objects.create(afiliado=self.perfil, amount=Decimal('888888'))

    def test_suma_lo_pagado_en_el_ano_neto_de_gastos(self):
        self.assertEqual(total_pagado_en_anio(self.perfil, 2026), Decimal('249000.00'))
        self.assertEqual(total_pagado_en_anio(self.perfil, 2025), Decimal('100000.00'))
        self.assertEqual(total_pagado_en_anio(self.perfil, 2024), Decimal('0.00'))

    def test_los_pagos_de_cada_ano_no_se_mezclan(self):
        self.assertEqual(
            totales_pagados_por_anio(self.perfil),
            [(2026, Decimal('249000.00'), 2), (2025, Decimal('100000.00'), 1)],
        )

    def test_el_ano_se_cuenta_en_la_zona_horaria_del_negocio(self):
        otro = self.comprador
        from .models import PerfilAfiliado
        perfil = PerfilAfiliado.objects.create(user=otro)
        tz = timezone.get_current_timezone()
        # 31 de diciembre, 8 p. m. en Bogota = 1 de enero en UTC.
        _pagada(perfil, '70000', datetime(2026, 12, 31, 20, tzinfo=tz))
        self.assertEqual(total_pagado_en_anio(perfil, 2026), Decimal('70000.00'))
        self.assertEqual(total_pagado_en_anio(perfil, 2027), Decimal('0.00'))

    def test_el_panel_del_afiliado_lo_muestra(self):
        self.client.force_login(self.afiliado_user)
        anio = timezone.localdate().year
        respuesta = self.client.get(reverse('afiliado_dashboard'))
        self.assertEqual(respuesta.context['pagado_en_el_anio'], total_pagado_en_anio(self.perfil, anio))
        self.assertContains(respuesta, f'Pagado en {anio}')
        # El detalle por ano y por mes vive en su propia pantalla.
        self.assertContains(respuesta, reverse('afiliado_pagos'))

    def test_el_detalle_del_admin_lo_muestra(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('admin_afiliado_detail', args=[self.perfil.pk]))
        self.assertContains(respuesta, 'No se aplican retenciones')
        self.assertContains(respuesta, reverse('admin_afiliado_pagos', args=[self.perfil.pk]))
        self.assertContains(respuesta, 'Ver historial de pagos')

    def test_el_listado_del_admin_no_lleva_la_columna_y_si_el_boton_de_pagos(self):
        anio = timezone.localdate().year
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('admin_afiliados'))
        self.assertNotContains(respuesta, f'Pagado {anio}')
        self.assertContains(respuesta, reverse('admin_afiliado_pagos', args=[self.perfil.pk]))


class HistorialDePagosTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.tz = timezone.get_current_timezone()
        _pagada(self.perfil, '100000', datetime(2025, 3, 10, 12, tzinfo=self.tz))
        _pagada(self.perfil, '200000', datetime(2026, 2, 5, 12, tzinfo=self.tz), gastos='1000')
        _pagada(self.perfil, '50000', datetime(2026, 2, 20, 12, tzinfo=self.tz))
        _pagada(self.perfil, '70000', datetime(2026, 8, 20, 12, tzinfo=self.tz))
        WithdrawalRequest.objects.create(
            afiliado=self.perfil, amount=Decimal('999999'), status=WithdrawalStatus.REJECTED,
            resolved_at=datetime(2026, 5, 1, tzinfo=self.tz),
        )
        self.url_admin = reverse('admin_afiliado_pagos', args=[self.perfil.pk])
        self.url_afiliado = reverse('afiliado_pagos')

    def test_el_desglose_trae_los_doce_meses_con_lo_pagado_en_cada_uno(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(self.url_admin, {'anio': '2026'})
        meses = respuesta.context['meses']
        self.assertEqual([m['mes'].month for m in meses], list(range(1, 13)))
        febrero, agosto, mayo = meses[1], meses[7], meses[4]
        self.assertEqual((febrero['cantidad'], febrero['bruto'], febrero['gastos'], febrero['neto']),
                         (2, Decimal('250000.00'), Decimal('1000.00'), Decimal('249000.00')))
        self.assertEqual((agosto['cantidad'], agosto['neto']), (1, Decimal('70000.00')))
        # Una solicitud rechazada no cuenta como pago.
        self.assertEqual((mayo['cantidad'], mayo['neto']), (0, Decimal('0.00')))
        self.assertEqual(respuesta.context['total_del_anio'], Decimal('319000.00'))
        self.assertEqual(respuesta.context['cantidad_del_anio'], 3)
        self.assertEqual(respuesta.context['total_historico'], Decimal('419000.00'))

    def test_la_pagina_muestra_los_meses_en_espanol_y_cada_pago(self):
        self.client.force_login(self.admin)
        html = self.client.get(self.url_admin, {'anio': '2026'}).content.decode()
        for mes in ('Enero', 'Febrero', 'Agosto', 'Diciembre'):
            self.assertIn(mes, html)
        self.assertIn('$249.000 COP', html)
        self.assertIn('05/02/2026', html)
        self.assertIn('20/08/2026', html)

    def test_el_titulo_lleva_el_nombre_y_entre_parentesis_el_codigo(self):
        self.perfil.first_name, self.perfil.last_name = 'Ana', 'Perez'
        self.perfil.save()
        self.client.force_login(self.admin)
        html = self.client.get(self.url_admin).content.decode()
        self.assertIn(f'Ana Perez ({self.perfil.referral_code})', html)
        self.assertNotIn(f'<h1>{self.afiliado_user.email}</h1>', html)

    def test_el_detalle_del_afiliado_usa_el_mismo_titulo(self):
        self.perfil.first_name, self.perfil.last_name = 'Ana', 'Perez'
        self.perfil.save()
        self.client.force_login(self.admin)
        html = self.client.get(reverse('admin_afiliado_detail', args=[self.perfil.pk])).content.decode()
        self.assertIn(f'<h1>Ana Perez ({self.perfil.referral_code})</h1>', html)
        # El correo sigue visible en el detalle como dato de contacto.
        self.assertIn(f'<strong>Correo:</strong> {self.afiliado_user.email}', html)

    def test_sin_nombre_el_titulo_usa_el_de_la_cuenta_o_el_correo(self):
        self.perfil.first_name = self.perfil.last_name = ''
        self.perfil.save()
        self.assertEqual(self.perfil.display_name, self.afiliado_user.email)
        self.afiliado_user.first_name, self.afiliado_user.last_name = 'Laura', 'Gomez'
        self.afiliado_user.save()
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.display_name, 'Laura Gomez')

    def test_se_puede_cambiar_de_ano_y_los_anos_no_se_mezclan(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(self.url_admin, {'anio': '2025'})
        self.assertEqual(respuesta.context['anio'], 2025)
        self.assertEqual(respuesta.context['meses'][2]['neto'], Decimal('100000.00'))
        self.assertEqual(respuesta.context['total_del_anio'], Decimal('100000.00'))
        self.assertEqual([p.amount for p in respuesta.context['pagos']], [Decimal('100000.00')])

    def test_el_filtro_de_ano_tolera_valores_invalidos(self):
        self.client.force_login(self.admin)
        actual = timezone.localdate().year
        for valor in ('abc', '', '1850', '9999', '-3'):
            with self.subTest(valor=valor):
                self.assertEqual(self.client.get(self.url_admin, {'anio': valor}).context['anio'], actual)

    def test_el_filtro_de_mes_deja_solo_ese_mes_en_totales_y_pagos(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(self.url_admin, {'anio': '2026', 'mes': '2'})
        self.assertEqual(respuesta.context['mes'], 2)
        self.assertEqual([m['mes'].month for m in respuesta.context['meses_a_mostrar']], [2])
        self.assertEqual([p.amount for p in respuesta.context['pagos']], [Decimal('50000.00'), Decimal('200000.00')])
        self.assertContains(respuesta, 'Recibido en febrero de 2026')
        self.assertContains(respuesta, '$249.000 COP')
        self.assertNotContains(respuesta, '20/08/2026')
        # Los doce meses siguen disponibles en el desplegable.
        self.assertEqual(len(respuesta.context['meses']), 12)

    def test_el_filtro_de_mes_tolera_valores_invalidos(self):
        self.client.force_login(self.admin)
        for valor in ('abc', '', '0', '13', '-1'):
            with self.subTest(valor=valor):
                respuesta = self.client.get(self.url_admin, {'anio': '2026', 'mes': valor})
                self.assertIsNone(respuesta.context['mes'])
                self.assertEqual(len(respuesta.context['meses_a_mostrar']), 12)

    def test_un_mes_sin_pagos_sale_en_cero_sin_errores(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(self.url_admin, {'anio': '2026', 'mes': '5'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No hay pagos registrados en mayo de 2026')

    def test_el_desplegable_de_anos_no_tiene_saltos_hasta_el_actual(self):
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(created_at=datetime(2023, 6, 1, tzinfo=self.tz))
        self.client.force_login(self.admin)
        anios = self.client.get(self.url_admin).context['anios']
        self.assertEqual(anios, list(range(timezone.localdate().year, 2022, -1)))

    def test_las_pestanas_incluyen_los_anos_con_pagos_y_el_actual(self):
        self.client.force_login(self.admin)
        anios = self.client.get(self.url_admin).context['anios']
        self.assertEqual(anios, sorted({2025, 2026, timezone.localdate().year}, reverse=True))

    def test_el_mes_se_cuenta_en_la_zona_horaria_del_negocio(self):
        otro = PerfilAfiliado.objects.create(user=self.comprador)
        # 31 de enero, 8 p. m. en Bogota = 1 de febrero en UTC.
        _pagada(otro, '30000', datetime(2026, 1, 31, 20, tzinfo=self.tz))
        self.client.force_login(self.admin)
        meses = self.client.get(reverse('admin_afiliado_pagos', args=[otro.pk]), {'anio': '2026'}).context['meses']
        self.assertEqual((meses[0]['cantidad'], meses[1]['cantidad']), (1, 0))

    def test_las_solicitudes_en_curso_se_listan_aparte(self):
        WithdrawalRequest.objects.create(afiliado=self.perfil, amount=Decimal('88000'))
        self.client.force_login(self.admin)
        respuesta = self.client.get(self.url_admin)
        self.assertEqual([s.amount for s in respuesta.context['solicitudes_en_curso']], [Decimal('88000.00')])
        self.assertContains(respuesta, 'Solicitudes en curso')

    def test_un_afiliado_sin_pagos_ve_la_pantalla_vacia_sin_errores(self):
        otro = PerfilAfiliado.objects.create(user=self.comprador)
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('admin_afiliado_pagos', args=[otro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No hay pagos registrados')

    def test_solo_el_equipo_ve_la_pantalla_del_admin(self):
        self.assertEqual(self.client.get(self.url_admin).status_code, 302)
        self.client.force_login(self.afiliado_user)
        self.assertEqual(self.client.get(self.url_admin).status_code, 302)

    def test_el_afiliado_ve_su_propio_historial(self):
        self.client.force_login(self.afiliado_user)
        respuesta = self.client.get(self.url_afiliado, {'anio': '2026'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['total_del_anio'], Decimal('319000.00'))
        self.assertContains(respuesta, 'Mis pagos')
        self.assertContains(respuesta, 'Febrero')

    def test_el_afiliado_no_ve_pagos_ajenos(self):
        otro = PerfilAfiliado.objects.create(user=self.comprador, status=EstadoAfiliado.APPROVED)
        _pagada(otro, '999000', datetime(2026, 2, 6, 12, tzinfo=self.tz))
        self.client.force_login(self.afiliado_user)
        respuesta = self.client.get(self.url_afiliado, {'anio': '2026'})
        self.assertNotContains(respuesta, '999.000')
        self.assertEqual(respuesta.context['total_del_anio'], Decimal('319000.00'))

    def test_quien_ya_salio_puede_ver_su_historial_y_quien_no_fue_aprobado_no(self):
        self.client.force_login(self.afiliado_user)
        deactivate_afiliado(self.perfil)
        self.assertEqual(self.client.get(self.url_afiliado).status_code, 200)
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(status=EstadoAfiliado.PENDING)
        self.assertRedirects(
            self.client.get(self.url_afiliado), reverse('afiliado_dashboard'), fetch_redirect_response=False,
        )

    def test_el_panel_lleva_al_historial_con_un_boton(self):
        self.client.force_login(self.afiliado_user)
        html = self.client.get(reverse('afiliado_dashboard')).content.decode()
        self.assertEqual(html.count(f'href="{self.url_afiliado}"'), 2)  # acciones y bloque de pagos
        self.assertIn('Ver historial de pagos', html)


class TasaDeComisionEnLosTerminosTests(AfiliadoTestBase):
    def test_la_tasa_por_defecto_es_la_que_prometen_los_terminos(self):
        ConfiguracionProgramaAfiliados.objects.all().delete()
        self.assertEqual(ConfiguracionProgramaAfiliados.load().default_commission_rate, COMISION_GLOBAL_EN_TERMINOS)
        self.assertEqual(COMISION_GLOBAL_EN_TERMINOS, Decimal('20.00'))

    def test_el_texto_publicado_dice_la_misma_cifra(self):
        html = self.client.get(reverse('afiliado_terminos')).content.decode()
        self.assertIn(f'<strong>{COMISION_GLOBAL_EN_TERMINOS:.0f} %</strong>', html)

    def test_la_migracion_lleva_la_tasa_antigua_a_20_y_respeta_las_editadas(self):
        migracion = importlib.import_module('afiliados.migrations.0012_tasa_global_de_los_terminos')
        for antes, despues in ((Decimal('10.00'), Decimal('20.00')), (Decimal('12.50'), Decimal('12.50')),
                               (Decimal('20.00'), Decimal('20.00'))):
            with self.subTest(antes=antes):
                ConfiguracionProgramaAfiliados.objects.update_or_create(pk=1, defaults={'default_commission_rate': antes})
                migracion.llevar_la_tasa_antigua_a_la_de_los_terminos(django_apps, None)
                self.assertEqual(ConfiguracionProgramaAfiliados.load().default_commission_rate, despues)

    def test_el_panel_avisa_si_la_tasa_global_se_aparta_de_los_terminos(self):
        self.client.force_login(self.admin)
        ConfiguracionProgramaAfiliados.objects.update_or_create(pk=1, defaults={'default_commission_rate': Decimal('20.00')})
        respuesta = self.client.get(reverse('admin_afiliados'))
        self.assertFalse(respuesta.context['tasa_difiere_de_los_terminos'])
        self.assertNotContains(respuesta, 'distinta de la que prometen')

        ConfiguracionProgramaAfiliados.objects.filter(pk=1).update(default_commission_rate=Decimal('15.00'))
        respuesta = self.client.get(reverse('admin_afiliados'))
        self.assertTrue(respuesta.context['tasa_difiere_de_los_terminos'])
        self.assertContains(respuesta, 'distinta de la que prometen')

    def test_el_formulario_de_configuracion_muestra_el_nombre_y_el_valor_actual(self):
        self.client.force_login(self.admin)
        self._dar_permisos_de_admin(self.admin)
        respuesta = self.client.get(reverse('admin_afiliados'))
        self.assertContains(respuesta, 'Tasa de comisión global (%)')
        self.assertContains(respuesta, 'value="20.00"')


class TitularDeLaCuentaTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.perfil.document_type, self.perfil.document_number = 'CC', '1020304050'
        self.perfil.first_name = 'Ana'
        self.perfil.save()
        self.client.force_login(self.afiliado_user)

    def _datos_cuenta(self, **cambios):
        datos = {
            'first_name': 'Ana', 'last_name': 'Perez', 'phone': '3001234567', 'address': 'Calle 1 # 2-3',
            'document_type': 'CC', 'document_number': '1020304050', 'breb_key': '3001234567',
            'accept_terms': '1', 'accept_data': '1',
        }
        datos.update(cambios)
        return datos

    def test_documento_igual_al_del_perfil_guarda_sin_advertencia(self):
        respuesta = self.client.post(reverse('afiliado_cuenta_pago'), self._datos_cuenta())
        self.assertIn('Ya puedes solicitar', _mensajes(respuesta)[-1])
        self.assertTrue(PayoutAccount.objects.get().documento_coincide_con_el_perfil)

    def test_documento_distinto_guarda_pero_advierte(self):
        respuesta = self.client.post(reverse('afiliado_cuenta_pago'), self._datos_cuenta(document_number='99887766'))
        self.assertIn('no coincide', _mensajes(respuesta)[-1])
        self.assertFalse(PayoutAccount.objects.get().documento_coincide_con_el_perfil)

    def test_el_panel_y_el_admin_muestran_la_alerta(self):
        self.client.post(reverse('afiliado_cuenta_pago'), self._datos_cuenta(document_number='99887766'))
        self.assertContains(self.client.get(reverse('afiliado_dashboard')), 'Revisa tu cuenta Bre-B')
        self.client.force_login(self.admin)
        self.assertContains(
            self.client.get(reverse('admin_afiliado_detail', args=[self.perfil.pk])), 'no coincide con el del perfil',
        )

    def test_un_perfil_sin_documento_no_se_advierte(self):
        self.perfil.document_number = ''
        self.perfil.save()
        cuenta = self._inscribir_cuenta(self.perfil)
        self.assertTrue(cuenta.documento_coincide_con_el_perfil)


class CobroDeQuienYaSalioTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self._inscribir_cuenta(self.perfil)
        self.client.force_login(self.afiliado_user)

    def test_tras_la_baja_conserva_lo_confirmado_y_puede_solicitarlo(self):
        self._pedido_entregado(self.perfil)
        deactivate_afiliado(self.perfil)
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_active)

        respuesta = self.client.get(reverse('afiliado_dashboard'))
        self.assertContains(respuesta, 'Tu suscripción está inactiva')
        self.assertContains(respuesta, 'Tus pagos')
        self.assertContains(respuesta, 'Solicitar comisión')

        self.client.post(reverse('afiliado_solicitar_retiro'))
        solicitud = WithdrawalRequest.objects.get(afiliado=self.perfil)
        self.assertEqual(solicitud.status, WithdrawalStatus.PENDING)

    def test_las_comisiones_en_validacion_siguen_madurando_tras_la_baja(self):
        pedido = self._pedido_entregado_en_validacion(self.perfil)
        deactivate_afiliado(self.perfil)

        confirmar_comisiones_vencidas(ahora=timezone.now() + timedelta(days=60))

        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.APPROVED)

    def test_quien_salio_puede_actualizar_su_cuenta_de_pago(self):
        deactivate_afiliado(self.perfil)
        respuesta = self.client.get(reverse('afiliado_cuenta_pago'))
        self.assertEqual(respuesta.status_code, 200)

    def test_quien_salio_no_ve_su_codigo_ni_el_resto_del_panel(self):
        deactivate_afiliado(self.perfil)
        html = self.client.get(reverse('afiliado_dashboard')).content.decode()
        self.assertNotIn(self.perfil.referral_code, html)
        self.assertNotIn('Compras referidas', html)

    def test_alguien_que_nunca_fue_aprobado_no_cobra(self):
        from .models import EstadoAfiliado, PerfilAfiliado
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(status=EstadoAfiliado.PENDING)
        respuesta = self.client.post(reverse('afiliado_solicitar_retiro'))
        self.assertRedirects(respuesta, reverse('afiliado_dashboard'), fetch_redirect_response=False)
        self.assertFalse(WithdrawalRequest.objects.exists())
