"""Saneamiento de la respuesta del Coach: solo sobrevive lo que la tienda puede
comprobar."""
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import translation
from inventory.models import Inventory
from products.models import ProductVariant

from . import contrato, paquete, respuesta
from .test_paquete import _con_carrito, _peticion
from .test_utilidades import aislar_catalogo, crear_producto


class SanearTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        self.producto, (self.talla_s, self.talla_m) = crear_producto(
            'Leggins Quantum',
            [
                ('S', 'gris', 2, {'price_override': Decimal('450000.0000')}),
                ('M', 'gris', 5, {
                    'price_override': Decimal('450000.0000'),
                    'discount_price': Decimal('400000.0000'),
                }),
            ],
        )
        self.otro, (self.otro_m,) = crear_producto('Camiseta', [('M', 'negro', 9)])

    def _solicitud(self, sesion=None, mensaje='hola'):
        with translation.override('es'):
            return paquete.armar_solicitud(_peticion(sesion=sesion), mensaje, 'shop-x', ahora=1)

    def _sanear(self, datos, solicitud=None):
        crudo = {'reply': 'Te recomiendo este.', 'meta': {'status': 'ok'}, **datos}
        with translation.override('es'):
            return respuesta.sanear(contrato.validar_respuesta(crudo), solicitud or self._solicitud())

    def _tipos(self, segura):
        return [a['type'] for a in segura.acciones]

    # --- acciones --------------------------------------------------------

    def test_agregar_al_carrito_se_reconstruye_con_datos_de_la_tienda(self):
        segura = self._sanear({'ui_actions': [
            {'type': 'add_to_cart', 'variant_id': self.talla_m.id, 'label': 'Gratis http://evil.example'},
        ]})

        accion = segura.acciones[0]
        self.assertEqual(accion['variant_id'], self.talla_m.id)
        self.assertEqual(accion['product_id'], self.producto.id)
        self.assertEqual(accion['endpoint'], f'/es/carrito/add/{self.talla_m.id}/')
        self.assertEqual(accion['label'], 'Agregar M · gris al carrito')
        self.assertEqual(accion['product_name'], 'Leggins Quantum')
        self.assertEqual(accion['variant_label'], 'M · gris')
        self.assertEqual(accion['price'], '$400.000 COP')
        self.assertNotIn('evil', str(segura.acciones))

    def test_una_variante_que_no_se_ofrecio_en_el_turno_se_descarta(self):
        # Existe, esta activa y tiene stock, pero no estaba entre los candidatos.
        solicitud = self._solicitud()
        for candidato in solicitud['evidence']['candidates']:
            candidato['variants'] = [v for v in candidato['variants'] if v['id'] != self.talla_s.id]

        segura = self._sanear(
            {'ui_actions': [{'type': 'add_to_cart', 'variant_id': self.talla_s.id}]}, solicitud,
        )

        self.assertEqual(segura.acciones, [])
        self.assertEqual(segura.descartadas, 1)

    def test_una_variante_que_se_agoto_despues_de_armar_el_paquete_se_descarta(self):
        solicitud = self._solicitud()
        Inventory.objects.filter(variant=self.talla_m).update(quantity_available=0)

        segura = self._sanear(
            {'ui_actions': [{'type': 'add_to_cart', 'variant_id': self.talla_m.id}]}, solicitud,
        )

        self.assertEqual(segura.acciones, [])

    def test_una_variante_desactivada_despues_de_armar_el_paquete_se_descarta(self):
        solicitud = self._solicitud()
        ProductVariant.objects.filter(pk=self.talla_m.pk).update(is_active=False)

        segura = self._sanear(
            {'ui_actions': [{'type': 'add_to_cart', 'variant_id': self.talla_m.id}]}, solicitud,
        )

        self.assertEqual(segura.acciones, [])

    def test_ids_inexistentes_se_descartan(self):
        segura = self._sanear({
            'ui_actions': [
                {'type': 'add_to_cart', 'variant_id': 999999},
                {'type': 'open_product', 'product_id': 999999},
            ],
            'product_cards': [{'product_id': 999999, 'reason': 'No existe'}],
        })

        self.assertEqual((segura.acciones, segura.tarjetas), ([], []))
        self.assertEqual(segura.descartadas, 3)

    def test_acciones_fuera_de_la_lista_blanca_no_llegan(self):
        segura = self._sanear({'ui_actions': [
            {'type': 'apply_coupon', 'code': 'GRATIS'},
            {'type': 'create_order'},
            {'type': 'update_profile', 'email': 'x@example.com'},
        ]})

        self.assertEqual(segura.acciones, [])

    def test_abrir_producto_usa_la_ruta_de_la_tienda(self):
        segura = self._sanear({'ui_actions': [{'type': 'open_product', 'product_id': self.producto.id}]})

        self.assertEqual(segura.acciones[0]['url'], f'/es/tienda/producto/{self.producto.id}/')
        self.assertEqual(segura.acciones[0]['label'], 'Ver Leggins Quantum')

    def test_ir_al_pago_exige_carrito_con_productos(self):
        sin_carrito = self._sanear({'ui_actions': [{'type': 'go_checkout'}]})
        con_carrito = self._sanear(
            {'ui_actions': [{'type': 'go_checkout'}]},
            self._solicitud(sesion=_con_carrito((self.talla_m, 1))),
        )

        self.assertEqual(sin_carrito.acciones, [])
        self.assertEqual(con_carrito.acciones[0]['url'], '/es/pedidos-tienda/checkout/')

    def test_con_las_compras_en_pausa_no_se_agrega_ni_se_va_al_pago(self):
        solicitud = self._solicitud(sesion=_con_carrito((self.talla_m, 1)))
        acciones = [
            {'type': 'add_to_cart', 'variant_id': self.talla_m.id},
            {'type': 'go_checkout'},
            {'type': 'open_product', 'product_id': self.producto.id},
        ]

        with mock.patch.object(respuesta, 'compras_pausadas', return_value=True):
            segura = self._sanear({'ui_actions': acciones}, solicitud)

        self.assertEqual(self._tipos(segura), ['open_product'])

    def test_no_se_repiten_acciones(self):
        segura = self._sanear({'ui_actions': [
            {'type': 'open_product', 'product_id': self.producto.id},
            {'type': 'open_product', 'product_id': self.producto.id},
            {'type': 'open_contact'},
            {'type': 'open_contact'},
        ]})

        self.assertEqual(self._tipos(segura), ['open_product', 'open_contact'])

    def test_abrir_contacto_apunta_a_la_pagina_de_contacto(self):
        segura = self._sanear({'ui_actions': [{'type': 'open_contact'}]})

        self.assertEqual(segura.acciones[0]['url'], '/es/contacto/')

    # --- tarjetas --------------------------------------------------------

    def test_las_tarjetas_salen_de_la_base_de_datos(self):
        segura = self._sanear({'product_cards': [
            {'product_id': self.producto.id, 'reason': 'Está en tu talla.'},
        ]})

        tarjeta = segura.tarjetas[0]
        self.assertEqual(tarjeta['name'], 'Leggins Quantum')
        self.assertEqual(tarjeta['price'], '$400.000 COP')
        self.assertEqual(tarjeta['url'], f'/es/tienda/producto/{self.producto.id}/')
        self.assertEqual(tarjeta['reason'], 'Está en tu talla.')

    def test_una_tarjeta_de_un_producto_que_no_se_ofrecio_se_descarta(self):
        solicitud = self._solicitud()
        solicitud['evidence']['candidates'] = [
            c for c in solicitud['evidence']['candidates'] if c['product_id'] != self.otro.id
        ]

        segura = self._sanear({'product_cards': [{'product_id': self.otro.id, 'reason': 'x'}]}, solicitud)

        self.assertEqual(segura.tarjetas, [])

    def test_una_tarjeta_de_un_producto_sin_variantes_activas_se_descarta(self):
        solicitud = self._solicitud()
        ProductVariant.objects.filter(product=self.otro).update(is_active=False)

        segura = self._sanear({'product_cards': [{'product_id': self.otro.id, 'reason': 'x'}]}, solicitud)

        self.assertEqual(segura.tarjetas, [])

    # --- afirmaciones ----------------------------------------------------

    def test_una_afirmacion_prohibida_rechaza_toda_la_respuesta(self):
        textos = [
            'Esta tela tiene secado rápido.',
            'Con SECADO RAPIDO y protección solar.',
            'Una prenda antimicrobiana.',
            'Es ecológica y duradera.',
            'Ofrece regulación térmica.',
        ]
        for texto in textos:
            with self.subTest(texto=texto), self.assertRaises(respuesta.RespuestaRechazada) as ctx:
                self._sanear({'reply': texto})
            self.assertEqual(ctx.exception.codigo, 'afirmacion_prohibida')

    def test_una_afirmacion_prohibida_en_el_motivo_de_una_tarjeta_tambien_rechaza(self):
        with self.assertRaises(respuesta.RespuestaRechazada):
            self._sanear({'product_cards': [{'product_id': self.producto.id, 'reason': 'Secado rápido'}]})

    def test_un_texto_normal_pasa_sin_cambios(self):
        segura = self._sanear({'reply': 'Tiene microfibra, según la descripción del producto.'})

        self.assertEqual(segura.texto, 'Tiene microfibra, según la descripción del producto.')

    def test_la_lista_de_prohibidas_es_la_del_paquete_del_turno(self):
        solicitud = self._solicitud()
        solicitud['evidence']['claims_policy']['prohibited'] = ['palabra especial']

        with self.assertRaises(respuesta.RespuestaRechazada):
            self._sanear({'reply': 'Una Palabra Especial aquí.'}, solicitud)

    # --- traspaso --------------------------------------------------------

    def test_un_traspaso_agrega_la_accion_de_contacto(self):
        segura = self._sanear({'handoff': {'category': 'queja', 'reason': 'Quiere hablar con alguien'}})

        self.assertEqual(segura.contacto['url'], '/es/contacto/')
        self.assertEqual(self._tipos(segura), ['open_contact'])

    def test_un_traspaso_no_duplica_la_accion_de_contacto(self):
        segura = self._sanear({
            'ui_actions': [{'type': 'open_contact'}],
            'handoff': {'category': 'queja', 'reason': ''},
        })

        self.assertEqual(self._tipos(segura), ['open_contact'])

    def test_el_motivo_del_traspaso_no_se_muestra(self):
        segura = self._sanear({'handoff': {'category': 'queja', 'reason': 'MOTIVO-INTERNO'}})

        self.assertNotIn('MOTIVO-INTERNO', str(segura))
