"""Facturacion con Alegra: contra un doble del cliente, sin red."""
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from integrations.alegra.alegra_client import AlegraError
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

from . import facturacion
from .forms import CheckoutForm
from .models import Invoice, InvoiceStatus, Order, OrderStatus, PaymentStatus
from .services import confirm_payment, create_order_from_cart

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
    'document_type': 'CC', 'document_number': '1020304050',
}

ALEGRA = {
    'ALEGRA_FACTURACION_ACTIVA': True,
    'ALEGRA_EMAIL': 'user@example.com',
    'ALEGRA_API_TOKEN': 'token',
    'ALEGRA_IVA_TAX_ID': '3',
    'ALEGRA_IVA_PORCENTAJE': '19',
    'ALEGRA_PRECIOS_INCLUYEN_IVA': True,
    'ALEGRA_NUMBER_TEMPLATE_ID': '14',
    'ALEGRA_CONSUMIDOR_FINAL_ID': '',
    'ALEGRA_ITEM_GENERICO_ID': '',
    'ALEGRA_FACTURAR_DESDE': '',
}


class _Transaccion:
    status = 'approved'


def _cliente_falso():
    cliente = MagicMock()
    cliente.find_contact.return_value = None
    cliente.create_contact.return_value = {'id': 77}
    cliente.find_item.return_value = None
    cliente.create_item.side_effect = [{'id': 501}, {'id': 502}]
    cliente.create_invoice.return_value = {
        'id': 900, 'numberTemplate': {'fullNumber': 'FE-1001'}, 'stamp': {'cufe': 'abc123'},
    }
    return cliente


@override_settings(**ALEGRA)
class FacturacionBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria factura')
        marca = Brand.objects.create(name='Marca factura')
        producto = Product.objects.create(
            name='Camiseta', category=categoria, brand=marca,
            base_price=Decimal('119000.0000'), stock=0,
        )
        cls.variante = ProductVariant.objects.create(
            product=producto, sku='FAC-001-M-NEG', size='M', color='negro',
        )
        Inventory.objects.create(variant=cls.variante, quantity_available=10)

    def setUp(self):
        correo = f'fac-{self._testMethodName[:30]}@example.com'
        self.usuario = get_user_model().objects.create_user(
            email=correo, username=correo, password='secret123',
        )
        self.cliente = _cliente_falso()
        parche = patch.object(facturacion.AlegraClient, 'from_settings', return_value=self.cliente)
        parche.start()
        self.addCleanup(parche.stop)

    def _pedido_pagado(self, datos=None, cantidad=2):
        with self.captureOnCommitCallbacks(execute=False):
            pedido = create_order_from_cart(
                self.usuario, {str(self.variante.pk): cantidad}, datos or DATOS,
            )
            confirm_payment(pedido, _Transaccion())
        pedido.refresh_from_db()
        return pedido


class ArmarFacturaTests(FacturacionBaseTestCase):
    def test_el_precio_con_iva_incluido_se_envia_sin_iva(self):
        pedido = self._pedido_pagado()
        cuerpo = facturacion.armar_factura(
            pedido, '77', {'FAC-001-M-NEG': '501', 'ENVIO': '502'}, hoy=date(2026, 10, 20),
        )
        linea = cuerpo['items'][0]
        self.assertEqual(linea['price'], 100000.0)
        self.assertEqual(linea['quantity'], 2)
        self.assertEqual(linea['tax'], [{'id': '3'}])
        self.assertEqual(linea['reference'], 'FAC-001-M-NEG')

    @override_settings(ALEGRA_PRECIOS_INCLUYEN_IVA=False)
    def test_el_precio_sin_iva_incluido_se_envia_tal_cual(self):
        pedido = self._pedido_pagado()
        cuerpo = facturacion.armar_factura(pedido, '77', {'FAC-001-M-NEG': '501', 'ENVIO': '502'})
        self.assertEqual(cuerpo['items'][0]['price'], 119000.0)

    @override_settings(ALEGRA_IVA_TAX_ID='')
    def test_sin_id_de_iva_no_hay_impuesto_ni_conversion(self):
        pedido = self._pedido_pagado()
        cuerpo = facturacion.armar_factura(pedido, '77', {'FAC-001-M-NEG': '501', 'ENVIO': '502'})
        self.assertEqual(cuerpo['items'][0]['price'], 119000.0)
        self.assertEqual(cuerpo['items'][0]['tax'], [])

    def test_el_envio_va_como_linea_sin_descuento(self):
        pedido = self._pedido_pagado()
        Order.objects.filter(pk=pedido.pk).update(
            shipping_cost=Decimal('11900'), discount_total=Decimal('23800'),
        )
        pedido.refresh_from_db()
        cuerpo = facturacion.armar_factura(pedido, '77', {'FAC-001-M-NEG': '501', 'ENVIO': '502'})
        producto, envio = cuerpo['items']
        # 23.800 de descuento sobre un subtotal de 238.000 es el 10 %.
        self.assertEqual(producto['discount'], 10.0)
        self.assertEqual(envio['reference'], 'ENVIO')
        self.assertEqual(envio['price'], 10000.0)
        self.assertEqual(envio['discount'], 0)

    def test_la_factura_se_emite_electronicamente_con_numeracion(self):
        pedido = self._pedido_pagado()
        cuerpo = facturacion.armar_factura(pedido, '77', {'FAC-001-M-NEG': '501', 'ENVIO': '502'})
        self.assertEqual(cuerpo['stamp'], {'generateStamp': True})
        self.assertEqual(cuerpo['numberTemplate'], {'id': '14'})
        self.assertEqual(cuerpo['client'], '77')
        self.assertEqual(cuerpo['purchaseOrderNumber'], pedido.order_number)
        self.assertEqual(cuerpo['status'], 'open')

    @override_settings(ALEGRA_EMITIR_ELECTRONICA=False, ALEGRA_NUMBER_TEMPLATE_ID='')
    def test_sin_emision_electronica_no_lleva_stamp_ni_numeracion(self):
        pedido = self._pedido_pagado()
        cuerpo = facturacion.armar_factura(pedido, '77', {'FAC-001-M-NEG': '501', 'ENVIO': '502'})
        self.assertNotIn('stamp', cuerpo)
        self.assertNotIn('numberTemplate', cuerpo)


class ContactoTests(FacturacionBaseTestCase):
    def test_persona_natural(self):
        contacto = facturacion.armar_contacto(self._pedido_pagado())
        self.assertEqual(contacto['identificationObject'], {'type': 'CC', 'number': '1020304050'})
        self.assertEqual(contacto['kindOfPerson'], 'PERSON_ENTITY')
        self.assertEqual(contacto['nameObject'], {'firstName': 'Ana', 'lastName': 'Marin'})
        self.assertEqual(contacto['address']['city'], 'Bogotá')
        self.assertEqual(contacto['email'], 'ana@example.com')

    def test_empresa_lleva_digito_de_verificacion(self):
        pedido = self._pedido_pagado({**DATOS, 'document_type': 'NIT', 'document_number': '900123456'})
        contacto = facturacion.armar_contacto(pedido)
        self.assertEqual(contacto['kindOfPerson'], 'LEGAL_ENTITY')
        self.assertEqual(contacto['identificationObject']['dv'], '8')
        self.assertEqual(contacto['name'], 'Ana Marin')

    def test_pasaporte_se_traduce_al_tipo_de_alegra(self):
        pedido = self._pedido_pagado({**DATOS, 'document_type': 'PA', 'document_number': 'AB123456'})
        self.assertEqual(facturacion.armar_contacto(pedido)['identificationObject']['type'], 'PP')

    def test_digito_de_verificacion_de_nits_conocidos(self):
        # NIT de la DIAN: 800197268-4.
        self.assertEqual(facturacion.digito_verificacion('800197268'), 4)
        self.assertEqual(facturacion.digito_verificacion('900123456'), 8)

    def test_nit_demasiado_largo_no_se_puede_facturar(self):
        with self.assertRaises(facturacion.FacturacionError):
            facturacion.digito_verificacion('1' * 20)


class EmitirFacturaTests(FacturacionBaseTestCase):
    def test_emite_y_guarda_el_resultado(self):
        pedido = self._pedido_pagado()

        estado = facturacion.emitir_factura(pedido.pk)

        self.assertEqual(estado, InvoiceStatus.ISSUED)
        factura = Invoice.objects.get(order=pedido)
        self.assertEqual(factura.status, InvoiceStatus.ISSUED)
        self.assertEqual(factura.alegra_invoice_id, '900')
        self.assertEqual(factura.alegra_contact_id, '77')
        self.assertEqual(factura.number, 'FE-1001')
        self.assertEqual(factura.cufe, 'abc123')
        self.assertEqual(factura.attempts, 1)
        self.assertIsNotNone(factura.issued_at)
        self.cliente.create_contact.assert_called_once()
        self.cliente.create_invoice.assert_called_once()

    def test_reutiliza_el_cliente_y_los_productos_existentes(self):
        self.cliente.find_contact.return_value = {'id': 12}
        self.cliente.find_item.return_value = {'id': 44}
        pedido = self._pedido_pagado()

        facturacion.emitir_factura(pedido.pk)

        self.cliente.create_contact.assert_not_called()
        self.cliente.create_item.assert_not_called()
        self.assertEqual(self.cliente.create_invoice.call_args.args[0]['client'], '12')
        self.assertEqual(self.cliente.create_invoice.call_args.args[0]['items'][0]['id'], '44')

    @override_settings(ALEGRA_ITEM_GENERICO_ID='9')
    def test_con_producto_generico_no_busca_ni_crea_productos(self):
        pedido = self._pedido_pagado()

        facturacion.emitir_factura(pedido.pk)

        self.cliente.find_item.assert_not_called()
        self.cliente.create_item.assert_not_called()
        self.assertEqual(self.cliente.create_invoice.call_args.args[0]['items'][0]['id'], '9')

    def test_no_emite_dos_veces(self):
        pedido = self._pedido_pagado()

        facturacion.emitir_factura(pedido.pk)
        segunda = facturacion.emitir_factura(pedido.pk)

        self.assertIsNone(segunda)
        self.cliente.create_invoice.assert_called_once()

    def test_no_factura_un_pedido_cancelado_aunque_el_pago_este_aprobado(self):
        pedido = self._pedido_pagado()
        Order.objects.filter(pk=pedido.pk).update(order_status=OrderStatus.CANCELLED)

        self.assertIsNone(facturacion.emitir_factura(pedido.pk))
        self.assertFalse(Invoice.objects.exists())

    def test_no_factura_un_pedido_sin_pagar(self):
        with self.captureOnCommitCallbacks(execute=False):
            pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)

        self.assertIsNone(facturacion.emitir_factura(pedido.pk))
        self.assertFalse(Invoice.objects.exists())

    @override_settings(ALEGRA_FACTURACION_ACTIVA=False)
    def test_desactivada_no_hace_nada(self):
        pedido = self._pedido_pagado()

        self.assertIsNone(facturacion.emitir_factura(pedido.pk))
        self.assertFalse(Invoice.objects.exists())

    @override_settings(ALEGRA_API_TOKEN='')
    def test_sin_credenciales_no_hace_nada(self):
        pedido = self._pedido_pagado()

        self.assertIsNone(facturacion.emitir_factura(pedido.pk))

    def test_un_error_de_alegra_deja_la_factura_fallida_sin_propagarse(self):
        self.cliente.create_invoice.side_effect = AlegraError('Alegra respondió 400: sin numeración', 400)
        pedido = self._pedido_pagado()

        estado = facturacion.emitir_factura(pedido.pk)

        self.assertEqual(estado, InvoiceStatus.FAILED)
        factura = Invoice.objects.get(order=pedido)
        self.assertEqual(factura.status, InvoiceStatus.FAILED)
        self.assertIn('sin numeración', factura.last_error)
        pedido.refresh_from_db()
        self.assertEqual(pedido.order_status, OrderStatus.CONFIRMED)

    def test_un_error_inesperado_no_filtra_su_detalle(self):
        self.cliente.create_invoice.side_effect = RuntimeError('token secreto')
        pedido = self._pedido_pagado()

        facturacion.emitir_factura(pedido.pk)

        self.assertNotIn('secreto', Invoice.objects.get(order=pedido).last_error)

    def test_sin_documento_ni_consumidor_final_falla_con_un_mensaje_claro(self):
        pedido = self._pedido_pagado({**DATOS, 'document_type': '', 'document_number': ''})

        facturacion.emitir_factura(pedido.pk)

        factura = Invoice.objects.get(order=pedido)
        self.assertEqual(factura.status, InvoiceStatus.FAILED)
        self.assertIn('documento', factura.last_error)
        self.cliente.create_invoice.assert_not_called()

    @override_settings(ALEGRA_CONSUMIDOR_FINAL_ID='1')
    def test_sin_documento_usa_el_contacto_de_consumidor_final(self):
        pedido = self._pedido_pagado({**DATOS, 'document_type': '', 'document_number': ''})

        facturacion.emitir_factura(pedido.pk)

        self.assertEqual(self.cliente.create_invoice.call_args.args[0]['client'], '1')
        self.cliente.create_contact.assert_not_called()
        self.assertEqual(Invoice.objects.get(order=pedido).status, InvoiceStatus.ISSUED)

    def test_reintenta_una_fallida_y_borra_el_borrador_que_dejo_alegra(self):
        self.cliente.find_item.side_effect = [None, None, {'id': 501}, {'id': 502}]
        self.cliente.create_invoice.side_effect = [
            AlegraError('falló la DIAN', 400, {'error': 'falló la DIAN', 'invoice': {'id': 321}}),
            {'id': 900, 'numberTemplate': {'fullNumber': 'FE-1002'}},
        ]
        pedido = self._pedido_pagado()

        facturacion.emitir_factura(pedido.pk)
        self.assertEqual(Invoice.objects.get(order=pedido).alegra_invoice_id, '321')
        estado = facturacion.emitir_factura(pedido.pk)

        self.assertEqual(estado, InvoiceStatus.ISSUED)
        self.cliente.delete_invoice.assert_called_once_with('321')
        factura = Invoice.objects.get(order=pedido)
        self.assertEqual(factura.alegra_invoice_id, '900')
        self.assertEqual(factura.attempts, 2)
        self.assertEqual(factura.last_error, '')

    def test_si_el_borrador_ya_no_existe_sigue_con_el_reintento(self):
        self.cliente.find_item.side_effect = [None, None, {'id': 501}, {'id': 502}]
        self.cliente.create_invoice.side_effect = [
            AlegraError('falló', 400, {'invoice': {'id': 321}}),
            {'id': 900},
        ]
        self.cliente.delete_invoice.side_effect = AlegraError('no existe', 404)
        pedido = self._pedido_pagado()

        facturacion.emitir_factura(pedido.pk)
        estado = facturacion.emitir_factura(pedido.pk)

        self.assertEqual(estado, InvoiceStatus.ISSUED)

    def test_una_factura_en_proceso_reciente_no_se_vuelve_a_reclamar(self):
        pedido = self._pedido_pagado()
        Invoice.objects.create(order=pedido, status=InvoiceStatus.PROCESSING)
        Invoice.objects.filter(order=pedido).update(last_attempt_at=facturacion.timezone.now())

        self.assertIsNone(facturacion.emitir_factura(pedido.pk))
        self.cliente.create_invoice.assert_not_called()

    def test_una_factura_en_proceso_abandonada_se_retoma(self):
        pedido = self._pedido_pagado()
        Invoice.objects.create(order=pedido, status=InvoiceStatus.PROCESSING)
        Invoice.objects.filter(order=pedido).update(
            last_attempt_at=facturacion.timezone.now() - facturacion.timedelta(minutes=30),
        )

        self.assertEqual(facturacion.emitir_factura(pedido.pk), InvoiceStatus.ISSUED)

    def test_confirmar_el_pago_encola_la_factura(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
            confirm_payment(pedido, _Transaccion())

        # La tarea se resuelve por su ruta al ejecutarse, asi que basta con
        # sustituir la funcion antes de lanzar los callbacks.
        with patch('orders.facturacion.emitir_factura') as emitir:
            for callback in callbacks:
                callback()
        emitir.assert_called_once_with(pedido.pk)


class DatosDelClienteYPagoTests(FacturacionBaseTestCase):
    def _pago(self, pedido, tipo=None, provider='mercadopago'):
        payload = {'payment': {'payment_type_id': tipo}} if tipo else {}
        return pedido.payment_transactions.create(
            provider=provider, payment_id='123', external_reference=pedido.order_number,
            status='approved', amount=pedido.total, idempotency_key=f'k-{pedido.pk}-{tipo}',
            raw_payload=payload,
        )

    def _cuerpo(self, pedido):
        return facturacion.armar_factura(
            pedido, '77', {'FAC-001-M-NEG': '501', 'ENVIO': '502'},
            pago=facturacion.pago_aprobado(pedido),
        )

    def test_tarjeta_de_credito_de_mercado_pago(self):
        pedido = self._pedido_pagado()
        self._pago(pedido, 'credit_card')
        cuerpo = self._cuerpo(pedido)
        self.assertEqual(cuerpo['paymentMethod'], 'CREDIT_CARD')
        self.assertIn('Mercado Pago (pago 123)', cuerpo['observations'])
        self.assertIn(pedido.order_number, cuerpo['observations'])

    def test_pse_de_mercado_pago_es_transferencia(self):
        pedido = self._pedido_pagado()
        self._pago(pedido, 'bank_transfer')
        self.assertEqual(self._cuerpo(pedido)['paymentMethod'], 'DEBIT_TRANSFER')

    def test_efectivo_de_mercado_pago(self):
        pedido = self._pedido_pagado()
        self._pago(pedido, 'ticket')
        self.assertEqual(self._cuerpo(pedido)['paymentMethod'], 'CASH')

    @override_settings(ALEGRA_MEDIO_DE_PAGO='INSTRUMENT_NOT_DEFINED')
    def test_un_tipo_desconocido_usa_el_medio_por_defecto(self):
        pedido = self._pedido_pagado()
        self._pago(pedido, 'account_money')
        self.assertEqual(self._cuerpo(pedido)['paymentMethod'], 'INSTRUMENT_NOT_DEFINED')

    def test_sin_transaccion_solo_menciona_el_pedido(self):
        pedido = self._pedido_pagado()
        cuerpo = self._cuerpo(pedido)
        self.assertEqual(cuerpo['paymentMethod'], 'INSTRUMENT_NOT_DEFINED')
        self.assertEqual(cuerpo['observations'], f'Pedido {pedido.order_number}.')

    def test_la_emision_usa_el_medio_de_pago_real(self):
        pedido = self._pedido_pagado()
        self._pago(pedido, 'debit_card')

        facturacion.emitir_factura(pedido.pk)

        self.assertEqual(self.cliente.create_invoice.call_args.args[0]['paymentMethod'], 'DEBIT_CARD')

    def test_sin_documento_en_el_pedido_se_usa_el_de_la_cuenta(self):
        get_user_model().objects.filter(pk=self.usuario.pk).update(
            document_type='NIT', document_number='900123456',
        )
        pedido = self._pedido_pagado({**DATOS, 'document_type': '', 'document_number': ''})

        contacto = facturacion.armar_contacto(pedido)
        facturacion.emitir_factura(pedido.pk)

        self.assertEqual(contacto['identificationObject']['type'], 'NIT')
        self.assertEqual(contacto['identificationObject']['number'], '900123456')
        self.cliente.find_contact.assert_called_once_with('900123456', dv='8')
        self.assertEqual(Invoice.objects.get(order=pedido).status, InvoiceStatus.ISSUED)

    def test_el_documento_del_pedido_gana_sobre_el_de_la_cuenta(self):
        get_user_model().objects.filter(pk=self.usuario.pk).update(
            document_type='CC', document_number='111111111',
        )
        pedido = self._pedido_pagado()
        self.assertEqual(facturacion.documento_de(pedido), ('CC', '1020304050'))

    def test_un_pedido_en_otra_moneda_no_se_factura(self):
        pedido = self._pedido_pagado()
        Order.objects.filter(pk=pedido.pk).update(currency='USD')

        facturacion.emitir_factura(pedido.pk)

        factura = Invoice.objects.get(order=pedido)
        self.assertEqual(factura.status, InvoiceStatus.FAILED)
        self.assertIn('COP', factura.last_error)
        self.cliente.create_invoice.assert_not_called()


class PrevisualizarFacturaTests(FacturacionBaseTestCase):
    def _ejecutar(self, numero):
        salida = StringIO()
        call_command('previsualizar_factura', numero, stdout=salida)
        return salida.getvalue()

    def test_imprime_el_cliente_y_la_factura_sin_llamar_a_alegra(self):
        pedido = self._pedido_pagado()

        texto = self._ejecutar(pedido.order_number)

        self.assertIn('<id-cliente-alegra>', texto)
        self.assertIn(f'"purchaseOrderNumber": "{pedido.order_number}"', texto)
        self.assertIn('"number": "1020304050"', texto)
        self.cliente.create_invoice.assert_not_called()
        self.cliente.create_contact.assert_not_called()
        self.assertFalse(Invoice.objects.exists())

    @override_settings(ALEGRA_FACTURACION_ACTIVA=False, ALEGRA_EMAIL='', ALEGRA_API_TOKEN='')
    def test_funciona_con_la_facturacion_apagada(self):
        pedido = self._pedido_pagado()
        self.assertIn('POST /invoices', self._ejecutar(pedido.order_number))

    def test_avisa_si_el_pedido_no_se_facturaria(self):
        with self.captureOnCommitCallbacks(execute=False):
            pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS)
        self.assertIn('no se facturaría', self._ejecutar(pedido.order_number))

    def test_un_pedido_sin_documento_lo_dice_en_vez_de_fallar(self):
        pedido = self._pedido_pagado({**DATOS, 'document_type': '', 'document_number': ''})
        self.assertIn('Cliente: no se puede armar', self._ejecutar(pedido.order_number))

    def test_un_pedido_inexistente_es_un_error_claro(self):
        with self.assertRaises(CommandError):
            self._ejecutar('NO-EXISTE')


class OrdenesPorFacturarTests(FacturacionBaseTestCase):
    def test_reintenta_las_ya_intentadas_y_no_toca_el_historico(self):
        historico = self._pedido_pagado()
        fallida = self._pedido_pagado()
        Invoice.objects.create(order=fallida, status=InvoiceStatus.FAILED, attempts=1)

        self.assertEqual(facturacion.ordenes_por_facturar(), [fallida.pk])
        self.assertNotIn(historico.pk, facturacion.ordenes_por_facturar())

    def test_no_reintenta_pasado_el_maximo_de_intentos(self):
        pedido = self._pedido_pagado()
        Invoice.objects.create(
            order=pedido, status=InvoiceStatus.FAILED, attempts=facturacion.MAX_INTENTOS,
        )

        self.assertEqual(facturacion.ordenes_por_facturar(), [])

    def test_no_incluye_las_ya_emitidas(self):
        pedido = self._pedido_pagado()
        Invoice.objects.create(order=pedido, status=InvoiceStatus.ISSUED)

        self.assertEqual(facturacion.ordenes_por_facturar(), [])

    @override_settings(ALEGRA_FACTURAR_DESDE='2000-01-01')
    def test_con_fecha_de_inicio_incluye_los_pagados_sin_factura(self):
        pedido = self._pedido_pagado()

        self.assertEqual(facturacion.ordenes_por_facturar(), [pedido.pk])

    @override_settings(ALEGRA_FACTURAR_DESDE='2999-01-01')
    def test_con_fecha_futura_no_incluye_ninguno(self):
        self._pedido_pagado()

        self.assertEqual(facturacion.ordenes_por_facturar(), [])

    def test_el_comando_emite_las_pendientes(self):
        pedido = self._pedido_pagado()
        Invoice.objects.create(order=pedido, status=InvoiceStatus.FAILED, attempts=1)

        call_command('emitir_facturas_pendientes', stdout=MagicMock())

        self.assertEqual(Invoice.objects.get(order=pedido).status, InvoiceStatus.ISSUED)

    @override_settings(ALEGRA_FACTURACION_ACTIVA=False)
    def test_el_comando_desactivado_no_hace_nada(self):
        pedido = self._pedido_pagado()
        Invoice.objects.create(order=pedido, status=InvoiceStatus.FAILED, attempts=1)

        call_command('emitir_facturas_pendientes', stdout=MagicMock())

        self.cliente.create_invoice.assert_not_called()


class CheckoutDocumentoTests(TestCase):
    BASE = {
        'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
        'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
        'address_line': 'Calle 100 # 15-20',
    }

    def _form(self, **extra):
        return CheckoutForm({**self.BASE, **extra})

    def test_el_documento_es_opcional(self):
        self.assertTrue(self._form().is_valid(), self._form().errors)

    def test_cedula_valida(self):
        form = self._form(document_type='CC', document_number='1.020.304.050')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['document_number'], '1020304050')

    def test_nit_con_digito_de_verificacion_se_guarda_sin_el(self):
        form = self._form(document_type='NIT', document_number='900.123.456-8')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['document_number'], '900123456')

    def test_numero_sin_tipo_se_rechaza(self):
        form = self._form(document_number='1020304050')
        self.assertFalse(form.is_valid())
        self.assertIn('document_type', form.errors)

    def test_tipo_sin_numero_se_rechaza(self):
        form = self._form(document_type='CC')
        self.assertFalse(form.is_valid())
        self.assertIn('document_number', form.errors)

    def test_cedula_con_letras_se_rechaza(self):
        form = self._form(document_type='CC', document_number='12AB5')
        self.assertFalse(form.is_valid())
        self.assertIn('document_number', form.errors)

    def test_pasaporte_admite_letras(self):
        form = self._form(document_type='PA', document_number='AB123456')
        self.assertTrue(form.is_valid(), form.errors)

    def test_el_documento_llega_al_pedido(self):
        categoria = ProductCategory.objects.create(name='Cat doc')
        marca = Brand.objects.create(name='Marca doc')
        producto = Product.objects.create(
            name='Prod doc', category=categoria, brand=marca, base_price=Decimal('50000'), stock=0,
        )
        variante = ProductVariant.objects.create(product=producto, sku='DOC-1', size='M', color='negro')
        Inventory.objects.create(variant=variante, quantity_available=3)

        pedido = create_order_from_cart(None, {str(variante.pk): 1}, DATOS)

        self.assertEqual(pedido.customer_document_type, 'CC')
        self.assertEqual(pedido.customer_document_number, '1020304050')
        self.assertEqual(PaymentStatus.PENDING, pedido.payment_status)
