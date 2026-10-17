"""Ciclo de vida del afiliado: revision, correos, baja con preaviso,
terminacion, inactividad, nueva version de los terminos y avisos."""
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from orders.services import get_usable_coupon

from . import terminos as modulo_terminos
from .models import (
    Commission,
    CommissionStatus,
    ConfiguracionProgramaAfiliados,
    EstadoAfiliado,
    MotivoSalida,
    PerfilAfiliado,
    ReferralClick,
    SocialNetwork,
)
from .services import (
    afiliado_operativo,
    afiliados_inactivos,
    aplicar_bajas_vencidas,
    avisar_cambio_de_tasa,
    cancelar_baja,
    deactivate_afiliado,
    necesita_reaceptar_terminos,
    solicitar_baja,
    ultima_actividad,
)
from .tests import AfiliadoTestBase, datos_postulacion


def _mensajes(respuesta):
    from django.contrib.messages import get_messages
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class RevisionDeLaPostulacionTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self._dar_permisos_de_admin(self.admin)

    def _postular(self):
        self.client.force_login(self.afiliado_user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('afiliado_suscribete'), datos_postulacion())
        return PerfilAfiliado.objects.get(user=self.afiliado_user)

    def test_postular_envia_un_correo_de_solicitud_recibida(self):
        self._postular()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.afiliado_user.email])
        self.assertIn('Recibimos tu solicitud', mail.outbox[0].subject)

    def test_aprobar_envia_correo_con_el_codigo_y_el_enlace(self):
        perfil = self._postular()
        mail.outbox.clear()
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin_afiliado_approve', args=[perfil.pk]))
        correo = mail.outbox[0]
        self.assertEqual(correo.to, [self.afiliado_user.email])
        self.assertIn('bienvenida', correo.subject)
        self.assertIn(f'?ref={perfil.referral_code}', correo.body)
        self.assertIn('publicidad', correo.body)

    def test_la_bienvenida_explica_el_descuento_la_comision_y_como_empezar(self):
        ConfiguracionProgramaAfiliados.objects.update_or_create(pk=1, defaults={
            'default_customer_discount': Decimal('12.50'), 'default_commission_rate': Decimal('18.00'),
            'minimum_payout': Decimal('150000'),
        })
        perfil = self._postular()
        mail.outbox.clear()
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin_afiliado_approve', args=[perfil.pk]))
        correo = mail.outbox[0]
        (html, tipo), = correo.alternatives
        self.assertEqual(tipo, 'text/html')
        for texto in (
            perfil.referral_code,
            'Descuento para quien compra: 12.5 % de descuento',
            'Comisión por venta: 18 % del subtotal del pedido',
            'Mínimo para cobrar: $150.000 COP',
            '5 días hábiles después de la entrega',
            'Inscribe tu cuenta Bre-B',
        ):
            with self.subTest(texto=texto):
                self.assertIn(texto, correo.body)
        self.assertIn('Te damos la bienvenida', html)
        self.assertIn('12.5 % de descuento', html)
        self.assertIn('Ir a mi panel', html)

    def test_la_bienvenida_usa_la_tasa_propia_del_afiliado_si_la_tiene(self):
        perfil = self._postular()
        PerfilAfiliado.objects.filter(pk=perfil.pk).update(commission_rate=Decimal('25.00'))
        mail.outbox.clear()
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin_afiliado_approve', args=[perfil.pk]))
        self.assertIn('Comisión por venta: 25 % del subtotal del pedido', mail.outbox[0].body)

    def test_rechazar_exige_motivo_lo_guarda_y_lo_envia(self):
        perfil = self._postular()
        mail.outbox.clear()
        self.client.force_login(self.admin)
        url = reverse('admin_afiliado_reject', args=[perfil.pk])

        self.client.post(url, {'reason': '   '})
        perfil.refresh_from_db()
        self.assertEqual(perfil.status, EstadoAfiliado.PENDING)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {'reason': 'No encontramos contenido de fitness'})
        perfil.refresh_from_db()
        self.assertEqual(perfil.rejection_reason, 'No encontramos contenido de fitness')
        self.assertIn('No encontramos contenido de fitness', mail.outbox[0].body)

        self.client.force_login(self.afiliado_user)
        self.assertContains(self.client.get(reverse('afiliado_dashboard')), 'No encontramos contenido de fitness')

    def test_aprobar_otra_vez_limpia_el_motivo_de_rechazo(self):
        perfil = self._postular()
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_afiliado_reject', args=[perfil.pk]), {'reason': 'X'})
        self.client.post(reverse('admin_afiliado_approve', args=[perfil.pk]))
        perfil.refresh_from_db()
        self.assertEqual(perfil.rejection_reason, '')

    def test_las_notas_internas_se_guardan_y_el_afiliado_no_las_ve(self):
        perfil = self._postular()
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_afiliado_notes_update', args=[perfil.pk]), {'review_notes': 'Buen contenido'})
        perfil.refresh_from_db()
        self.assertEqual(perfil.review_notes, 'Buen contenido')
        self.assertContains(self.client.get(reverse('admin_afiliado_detail', args=[perfil.pk])), 'Buen contenido')
        self.client.force_login(self.afiliado_user)
        self.assertNotContains(self.client.get(reverse('afiliado_dashboard')), 'Buen contenido')

    def test_el_revisor_abre_el_perfil_de_cada_red_con_un_clic(self):
        perfil = self._postular()
        perfil.social_networks.all().delete()
        SocialNetwork.objects.create(afiliado=perfil, platform='instagram', username='anafit', followers=10)
        SocialNetwork.objects.create(afiliado=perfil, platform='tiktok', username='ana.fit', followers=10)
        SocialNetwork.objects.create(afiliado=perfil, platform='other', other_name='Kwai', username='ana', followers=10)
        self.client.force_login(self.admin)
        html = self.client.get(reverse('admin_afiliado_detail', args=[perfil.pk])).content.decode()
        self.assertIn('href="https://www.instagram.com/anafit/"', html)
        self.assertIn('href="https://www.tiktok.com/@ana.fit"', html)
        self.assertEqual(SocialNetwork.objects.get(platform='other').profile_url, '')


class BajaConPreavisoTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)

    def test_solicitar_la_baja_registra_el_aviso_y_no_desactiva_nada(self):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('afiliado_quitar_suscripcion'))

        self.assertRedirects(respuesta, reverse('afiliado_dashboard'), fetch_redirect_response=False)
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.is_active)
        self.assertTrue(self.perfil.baja_solicitada)
        self.assertEqual(self.perfil.exit_effective_at - self.perfil.exit_requested_at, timedelta(days=15))
        self.assertTrue(get_usable_coupon(self.perfil.referral_code, user=self.comprador))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('15 días', mail.outbox[0].body)

    def test_el_panel_muestra_la_baja_programada_y_deja_cancelarla(self):
        self.client.post(reverse('afiliado_quitar_suscripcion'))
        self.perfil.refresh_from_db()
        html = self.client.get(reverse('afiliado_dashboard')).content.decode()
        self.assertIn('Tu baja esta programada', html)
        self.assertIn(f'{timezone.localtime(self.perfil.exit_effective_at):%d/%m/%Y}', html)

        self.client.post(reverse('afiliado_cancelar_baja'))
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.baja_solicitada)
        self.assertIsNone(self.perfil.exit_effective_at)

    def test_pedir_la_baja_dos_veces_no_mueve_la_fecha(self):
        solicitar_baja(self.perfil)
        original = self.perfil.exit_effective_at
        solicitar_baja(self.perfil, ahora=timezone.now() + timedelta(days=5))
        self.assertEqual(self.perfil.exit_effective_at, original)

    def test_antes_de_vencer_el_preaviso_no_se_aplica_la_baja(self):
        solicitar_baja(self.perfil)
        self.assertEqual(aplicar_bajas_vencidas(ahora=timezone.now() + timedelta(days=14)), 0)
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.is_active)

    def test_al_vencer_el_preaviso_se_desactiva_el_codigo_y_se_avisa(self):
        solicitar_baja(self.perfil)
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(aplicar_bajas_vencidas(ahora=timezone.now() + timedelta(days=16)), 1)

        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_active)
        self.assertEqual(self.perfil.exit_reason, MotivoSalida.VOLUNTARY)
        self.assertIsNotNone(self.perfil.exited_at)
        self.assertFalse(self.perfil.coupons.first().is_active)
        self.assertFalse(self.perfil.user.es_afiliado)
        self.assertIn('ya es efectiva', mail.outbox[0].subject)

    def test_el_codigo_deja_de_valer_al_vencer_el_preaviso_aunque_la_baja_no_se_haya_aplicado(self):
        solicitar_baja(self.perfil)
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(exit_effective_at=timezone.now() - timedelta(minutes=1))
        self.perfil.refresh_from_db()
        self.assertFalse(afiliado_operativo(self.perfil))
        self.assertIsNone(get_usable_coupon(self.perfil.referral_code, user=self.comprador))

    def test_abrir_el_panel_aplica_la_baja_vencida_sin_tarea_programada(self):
        solicitar_baja(self.perfil)
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(exit_effective_at=timezone.now() - timedelta(days=1))
        self.client.get(reverse('afiliado_dashboard'))
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_active)

    def test_el_comando_aplica_las_bajas_vencidas(self):
        solicitar_baja(self.perfil)
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(exit_effective_at=timezone.now() - timedelta(days=1))
        call_command('aplicar_bajas', stdout=_Salida())
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_active)

    def test_quien_solo_tiene_una_solicitud_en_revision_la_cancela_al_instante(self):
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(status=EstadoAfiliado.PENDING)
        self.client.post(reverse('afiliado_quitar_suscripcion'))
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_active)
        self.assertIsNone(self.perfil.exit_requested_at)

    def test_cancelar_la_baja_sin_aviso_no_hace_nada(self):
        cancelar_baja(self.perfil)
        self.assertTrue(self.perfil.is_active)

    def test_la_baja_no_se_pide_con_un_get(self):
        self.client.get(reverse('afiliado_quitar_suscripcion'))
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.baja_solicitada)

    def test_el_admin_puede_adelantar_la_baja(self):
        solicitar_baja(self.perfil)
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin_afiliado_advance_exit', args=[self.perfil.pk]))
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_active)
        self.assertEqual(self.perfil.exit_reason, MotivoSalida.VOLUNTARY)

    def test_adelantar_sin_aviso_de_baja_no_hace_nada(self):
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_afiliado_advance_exit', args=[self.perfil.pk]))
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.is_active)

    def test_volver_a_aprobar_limpia_la_salida(self):
        solicitar_baja(self.perfil)
        deactivate_afiliado(self.perfil)
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_afiliado_approve', args=[self.perfil.pk]))
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.is_active)
        self.assertIsNone(self.perfil.exit_requested_at)
        self.assertEqual(self.perfil.exit_reason, '')


class _Salida:
    """Descarta lo que escribe un comando de gestion."""

    def write(self, *_):
        pass

    def flush(self):
        pass


class TerminacionPorGoToGymTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        self.url = reverse('admin_afiliado_terminate', args=[self.perfil.pk])

    def test_exige_un_motivo_valido(self):
        for datos in ({}, {'reason': 'voluntary'}, {'reason': 'inventado'}):
            with self.subTest(datos=datos):
                self.client.post(self.url, datos)
                self.perfil.refresh_from_db()
                self.assertTrue(self.perfil.is_active)

    def test_desactiva_el_codigo_registra_el_motivo_y_avisa(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {'reason': 'fraud', 'notes': 'Uso del codigo en sitios de cupones'})
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_active)
        self.assertEqual(self.perfil.exit_reason, MotivoSalida.FRAUD)
        self.assertEqual(self.perfil.exit_notes, 'Uso del codigo en sitios de cupones')
        self.assertFalse(self.perfil.coupons.first().is_active)
        correo = mail.outbox[0]
        self.assertIn('Terminamos tu participación', correo.subject)
        self.assertIn('sitios de cupones', correo.body)

    def test_puede_anular_las_comisiones_sin_pagar_pero_no_las_pagadas(self):
        from .services import request_withdrawal, resolve_withdrawal

        self._pedido_entregado(self.perfil)
        resolve_withdrawal(request_withdrawal(self.perfil), True, self.admin)
        pendiente = self._pedido_entregado_en_validacion(self.perfil)
        confirmada = self._pedido_entregado(self.perfil)

        self.client.post(self.url, {'reason': 'fraud', 'void_commissions': 'on'})

        estados = {c.order_id: c.status for c in Commission.objects.filter(afiliado=self.perfil)}
        self.assertEqual(estados[pendiente.pk], CommissionStatus.REVERTED)
        self.assertEqual(estados[confirmada.pk], CommissionStatus.REVERTED)
        self.assertEqual(list(estados.values()).count(CommissionStatus.PAID), 1)

    def test_sin_la_casilla_las_comisiones_siguen_su_curso(self):
        pedido = self._pedido_entregado(self.perfil)
        self.client.post(self.url, {'reason': 'breach'})
        self.assertEqual(Commission.objects.get(order=pedido).status, CommissionStatus.APPROVED)

    def test_el_detalle_muestra_como_salio(self):
        self.client.post(self.url, {'reason': 'inactivity'})
        self.assertContains(
            self.client.get(reverse('admin_afiliado_detail', args=[self.perfil.pk])),
            'Inactividad prolongada',
        )

    def test_sin_permiso_no_se_puede_terminar(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        intermedio = get_user_model().objects.create_user(
            email='intermedio@example.com', username='intermedio@example.com', password='secret123', is_staff=True,
        )
        intermedio.groups.add(Group.objects.create(name='Grupo sin permisos de afiliados'))
        self.client.force_login(intermedio)
        self.client.post(self.url, {'reason': 'fraud'})
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.is_active)


class InactividadTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()

    def _envejecer(self, dias):
        antes = timezone.now() - timedelta(days=dias)
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(reviewed_at=antes, created_at=antes)
        self.perfil.refresh_from_db()

    def test_sin_clics_ni_ventas_cuenta_desde_la_aprobacion(self):
        self._envejecer(100)
        self.assertEqual([p.pk for p, _ in afiliados_inactivos()], [self.perfil.pk])

    def test_un_afiliado_reciente_no_esta_inactivo(self):
        self.assertEqual(afiliados_inactivos(), [])

    def test_un_clic_reciente_lo_mantiene_activo(self):
        self._envejecer(100)
        ReferralClick.objects.create(afiliado=self.perfil)
        self.assertEqual(afiliados_inactivos(), [])
        self.assertGreater(ultima_actividad(self.perfil), timezone.now() - timedelta(minutes=1))

    def test_una_venta_reciente_lo_mantiene_activo(self):
        self._envejecer(100)
        self._pedido_entregado_en_validacion(self.perfil)
        self.assertEqual(afiliados_inactivos(), [])

    def test_el_umbral_sale_de_la_configuracion(self):
        from .models import ConfiguracionProgramaAfiliados
        self._envejecer(40)
        self.assertEqual(afiliados_inactivos(), [])
        ConfiguracionProgramaAfiliados.objects.filter(pk=1).update(inactivity_days=30)
        self.assertEqual(len(afiliados_inactivos()), 1)

    def test_quien_ya_salio_o_esta_pendiente_no_se_lista(self):
        self._envejecer(100)
        deactivate_afiliado(self.perfil)
        self.assertEqual(afiliados_inactivos(), [])

    def test_el_listado_del_admin_filtra_inactivos_y_muestra_la_ultima_actividad(self):
        self._envejecer(100)
        otro = PerfilAfiliado.objects.create(user=self.comprador, status=EstadoAfiliado.APPROVED)
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse('admin_afiliados'), {'inactivos': '1'})

        perfiles = [p.pk for p in respuesta.context['page_obj']]
        self.assertEqual(perfiles, [self.perfil.pk])
        self.assertNotIn(otro.pk, perfiles)
        self.assertContains(respuesta, 'Ultima actividad')
        self.assertContains(respuesta, f'mailto:{self.afiliado_user.email}')


class NuevaVersionDeLosTerminosTests(AfiliadoTestBase):
    exigir_terminos_vigentes = True

    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)

    def test_quien_no_tiene_la_version_vigente_debe_aceptarla_para_usar_el_panel(self):
        for ruta in ('afiliado_dashboard', 'afiliado_compras_referidas', 'afiliado_cuenta_pago', 'afiliado_editar_perfil', 'afiliado_recursos'):
            with self.subTest(ruta=ruta):
                self.assertRedirects(
                    self.client.get(reverse(ruta)), reverse('afiliado_aceptar_terminos'), fetch_redirect_response=False,
                )

    def test_aceptar_registra_la_version_y_devuelve_el_acceso(self):
        respuesta = self.client.get(reverse('afiliado_aceptar_terminos'))
        self.assertContains(respuesta, modulo_terminos.VERSION_TERMINOS_AFILIADOS)

        sin_marcar = self.client.post(reverse('afiliado_aceptar_terminos'), {})
        self.assertEqual(sin_marcar.status_code, 200)
        self.perfil.refresh_from_db()
        self.assertNotEqual(self.perfil.terms_version, modulo_terminos.VERSION_TERMINOS_AFILIADOS)

        self.client.post(reverse('afiliado_aceptar_terminos'), {'accept_terms': 'on'})
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.terms_version, modulo_terminos.VERSION_TERMINOS_AFILIADOS)
        self.assertEqual(self.client.get(reverse('afiliado_dashboard')).status_code, 200)

    def test_con_la_version_vigente_no_se_pide_nada(self):
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(terms_version=modulo_terminos.VERSION_TERMINOS_AFILIADOS)
        self.assertEqual(self.client.get(reverse('afiliado_dashboard')).status_code, 200)
        self.assertRedirects(
            self.client.get(reverse('afiliado_aceptar_terminos')), reverse('afiliado_dashboard'),
            fetch_redirect_response=False,
        )

    def test_al_subir_la_version_se_vuelve_a_pedir(self):
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(terms_version='1.0')
        self.perfil.refresh_from_db()
        original = modulo_terminos.VERSION_TERMINOS_AFILIADOS
        try:
            modulo_terminos.VERSION_TERMINOS_AFILIADOS = '2.0'
            from . import services
            services.VERSION_TERMINOS_AFILIADOS = '2.0'
            self.assertTrue(necesita_reaceptar_terminos(self.perfil))
        finally:
            modulo_terminos.VERSION_TERMINOS_AFILIADOS = original
            services.VERSION_TERMINOS_AFILIADOS = original

    def test_quien_ya_salio_o_espera_aprobacion_no_debe_aceptar(self):
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(status=EstadoAfiliado.PENDING)
        self.assertEqual(self.client.get(reverse('afiliado_dashboard')).status_code, 200)
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(status=EstadoAfiliado.APPROVED, is_active=False)
        self.perfil.refresh_from_db()
        self.assertFalse(necesita_reaceptar_terminos(self.perfil))
        self.assertEqual(self.client.get(reverse('afiliado_dashboard')).status_code, 200)

    def test_quien_no_acepta_puede_pedir_su_baja_desde_esa_pantalla(self):
        self.client.post(reverse('afiliado_quitar_suscripcion'))
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.baja_solicitada)
        self.assertContains(self.client.get(reverse('afiliado_aceptar_terminos')), 'aviso de baja')


class AvisosAProgramaTests(AfiliadoTestBase):
    def setUp(self):
        super().setUp()
        self.perfil = self._crear_perfil_aprobado()
        PerfilAfiliado.objects.create(user=self.comprador, status=EstadoAfiliado.PENDING)
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)

    def test_el_admin_avisa_solo_a_los_afiliados_activos(self):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(
                reverse('admin_afiliados_notify'),
                {'subject': 'Nuevos terminos', 'message': 'Actualizamos los terminos del programa.'},
            )
        self.assertEqual([m.to for m in mail.outbox], [[self.afiliado_user.email]])
        self.assertEqual(mail.outbox[0].subject, 'Nuevos terminos')
        self.assertIn('Actualizamos los terminos', mail.outbox[0].body)
        self.assertIn('1 afiliado', _mensajes(respuesta)[-1])

    def test_el_aviso_exige_asunto_y_mensaje(self):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('admin_afiliados_notify'), {'subject': 'Solo asunto', 'message': ''})
        self.assertEqual(mail.outbox, [])
        self.assertIn('asunto y el mensaje', _mensajes(respuesta)[-1])

    def test_cambiar_la_tasa_global_avisa_a_quienes_la_usan(self):
        propia = PerfilAfiliado.objects.create(user=self.admin, status=EstadoAfiliado.APPROVED)
        propia.commission_rate = 30
        propia.save()
        datos = {'default_commission_rate': '25.00', 'default_customer_discount': '10.00', 'minimum_payout': '100000', 'inactivity_days': '90'}
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin_afiliado_settings_update'), datos)
        self.assertEqual([m.to for m in mail.outbox], [[self.afiliado_user.email]])
        self.assertIn('25.00 %', mail.outbox[0].body)
        self.assertIn('ya registradas conservan', mail.outbox[0].body)

    def test_guardar_la_configuracion_sin_cambiar_la_tasa_no_envia_nada(self):
        datos = {'default_commission_rate': '20.00', 'default_customer_discount': '10.00', 'minimum_payout': '150000', 'inactivity_days': '90'}
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin_afiliado_settings_update'), datos)
        self.assertEqual(mail.outbox, [])

    def test_cambiar_la_tasa_propia_avisa_a_ese_afiliado(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('admin_afiliado_commission_rate_update', args=[self.perfil.pk]), {'commission_rate': '35'})
        self.assertEqual([m.to for m in mail.outbox], [[self.afiliado_user.email]])
        self.assertIn('35', mail.outbox[0].body)

    def test_avisar_de_un_cambio_de_tasa_a_un_afiliado_concreto(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(avisar_cambio_de_tasa('18', afiliado=self.perfil), 1)
        self.assertEqual(len(mail.outbox), 1)
