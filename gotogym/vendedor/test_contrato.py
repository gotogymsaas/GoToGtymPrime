"""Contrato tienda-Coach: forma de la solicitud y de la respuesta."""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from . import contrato

EJEMPLOS = Path(__file__).resolve().parent / 'ejemplos'


def _ejemplo(nombre):
    return json.loads((EJEMPLOS / nombre).read_text(encoding='utf-8'))


class SolicitudTests(SimpleTestCase):
    def setUp(self):
        self.solicitud = _ejemplo('solicitud.json')

    def _rechaza(self, prefijo):
        """La solicitud se rechaza y el error empieza por `prefijo` (la ruta
        del campo). Devuelve el mensaje."""
        with self.assertRaises(contrato.ContratoInvalido) as ctx:
            contrato.validar_solicitud(self.solicitud)
        mensaje = str(ctx.exception)
        self.assertTrue(mensaje.startswith(prefijo), mensaje)
        return mensaje

    def test_el_ejemplo_del_contrato_es_valido(self):
        contrato.validar_solicitud(self.solicitud)

    def test_la_serializacion_es_estable(self):
        self.assertEqual(contrato.serializar(self.solicitud), contrato.serializar(copy.deepcopy(self.solicitud)))

    def test_el_ejemplo_cabe_en_el_presupuesto(self):
        self.assertLess(contrato.tamano_en_bytes(self.solicitud), contrato.MAX_BYTES_SOLICITUD)

    def test_mensaje_vacio_o_demasiado_largo(self):
        for mensaje in ('', '   ', 'a' * (contrato.MAX_LARGO_MENSAJE + 1)):
            with self.subTest(largo=len(mensaje)):
                self.solicitud['message'] = mensaje
                self._rechaza('message')

    def test_idioma_no_soportado(self):
        self.solicitud['locale'] = 'pt'
        self._rechaza('locale')

    def test_el_sujeto_debe_ser_un_seudonimo_de_la_tienda(self):
        for sujeto in ('ana@example.com', 'visitante-1', ''):
            with self.subTest(sujeto=sujeto):
                self.solicitud['visitor']['subject'] = sujeto
                self._rechaza('visitor')

    def test_el_precio_debe_ser_texto_decimal(self):
        for precio in (400000.0, 400000, '400,50', '$400000', '-5', '1e5', ''):
            with self.subTest(precio=precio):
                self.solicitud['cart']['subtotal'] = precio
                self._rechaza('cart')

    def test_precio_de_variante_como_float_se_rechaza(self):
        self.solicitud['evidence']['candidates'][0]['variants'][0]['price'] = 400000.0
        self._rechaza('evidence')

    def test_los_booleanos_no_valen_como_enteros(self):
        self.solicitud['cart']['count'] = True
        self._rechaza('cart')

    def test_campos_de_datos_personales_se_rechazan_en_cualquier_nivel(self):
        for contenedor, campo in (
            (lambda s: s, 'email'),
            (lambda s: s['visitor'], 'telefono'),
            (lambda s: s['evidence']['candidates'][0], 'referral_code'),
            (lambda s: s['cart']['lines'][0], 'direccion'),
        ):
            with self.subTest(campo=campo):
                self.solicitud = copy.deepcopy(_ejemplo('solicitud.json'))
                contenedor(self.solicitud)[campo] = 'x'
                mensaje = self._rechaza('solicitud')
                self.assertTrue(mensaje.endswith(campo), mensaje)

    def test_demasiados_candidatos(self):
        candidato = self.solicitud['evidence']['candidates'][0]
        self.solicitud['evidence']['candidates'] = [candidato] * (contrato.MAX_CANDIDATOS + 1)
        self._rechaza('evidence')

    def test_un_candidato_sin_variantes_se_rechaza(self):
        self.solicitud['evidence']['candidates'][0]['variants'] = []
        self._rechaza('evidence')

    def test_la_url_del_candidato_debe_ser_interna(self):
        self.solicitud['evidence']['candidates'][0]['url'] = 'https://otro.example/x'
        self._rechaza('evidence')

    def test_la_descripcion_tiene_tope(self):
        self.solicitud['evidence']['candidates'][0]['description'] = 'x' * (contrato.MAX_LARGO_DESCRIPCION + 1)
        self._rechaza('evidence')

    def test_estado_de_revision_de_politica_desconocido(self):
        self.solicitud['evidence']['policies'][0]['review_status'] = 'aprobada'
        self._rechaza('evidence')

    def test_moneda_distinta_de_cop(self):
        self.solicitud['shop_flags']['currency'] = 'USD'
        self._rechaza('shop_flags')

    def test_conversation_id_debe_tener_el_prefijo_de_la_tienda(self):
        self.solicitud['conversation_id'] = 'otro-123'
        self._rechaza('conversation_id')

    def test_supera_el_presupuesto_de_tamano(self):
        # Cada campo respeta su propio tope, pero todos al maximo a la vez: el
        # total no cabe y debe fallar por tamano, no por un campo.
        candidato = copy.deepcopy(self.solicitud['evidence']['candidates'][0])
        candidato['name'] = 'n' * 150
        candidato['description'] = 'd' * contrato.MAX_LARGO_DESCRIPCION
        candidato['variants'] = candidato['variants'] * 12
        self.solicitud['evidence']['candidates'] = [candidato] * contrato.MAX_CANDIDATOS
        self.solicitud['evidence']['policies'] = [
            {**self.solicitud['evidence']['policies'][0], 'text': 'p' * contrato.MAX_LARGO_POLITICA}
        ] * contrato.MAX_POLITICAS
        self.solicitud['cart']['lines'] = self.solicitud['cart']['lines'] * contrato.MAX_LINEAS_CARRITO
        self.solicitud['message'] = 'm' * contrato.MAX_LARGO_MENSAJE
        self.assertGreater(contrato.tamano_en_bytes(self.solicitud), contrato.MAX_BYTES_SOLICITUD)

        mensaje = self._rechaza('solicitud')

        self.assertEqual(mensaje, 'solicitud.tamano')

    def test_el_error_nombra_el_campo_y_no_el_valor(self):
        self.solicitud['message'] = 'x' * (contrato.MAX_LARGO_MENSAJE + 1)

        mensaje = self._rechaza('message')

        self.assertNotIn('xxxx', mensaje)


class RespuestaTests(SimpleTestCase):
    def setUp(self):
        self.datos = _ejemplo('respuesta_ok.json')

    def test_el_ejemplo_del_contrato_es_valido(self):
        respuesta = contrato.validar_respuesta(self.datos)

        self.assertTrue(respuesta.ok)
        self.assertEqual([a.tipo for a in respuesta.acciones], ['add_to_cart', 'open_product'])
        self.assertEqual(respuesta.acciones[0].variant_id, 31)
        self.assertEqual(respuesta.tarjetas[0].product_id, 12)
        self.assertEqual(respuesta.descartadas, 0)
        self.assertEqual(respuesta.meta.agentes, ('discovery', 'fit'))

    def test_el_ejemplo_de_error_es_valido(self):
        respuesta = contrato.validar_respuesta(_ejemplo('respuesta_error.json'))

        self.assertFalse(respuesta.ok)
        self.assertEqual(respuesta.meta.reintentar_en, 20)
        self.assertEqual(respuesta.texto, '')

    def test_en_error_se_ignora_cualquier_texto_o_accion(self):
        self.datos['meta']['status'] = 'error'

        respuesta = contrato.validar_respuesta(self.datos)

        self.assertEqual(respuesta.texto, '')
        self.assertEqual(respuesta.acciones, ())

    def test_acciones_fuera_de_la_lista_blanca_se_descartan(self):
        self.datos['ui_actions'] = [
            {'type': 'apply_coupon', 'code': 'GRATIS'},
            {'type': 'create_order'},
            {'type': 'add_to_cart', 'variant_id': 31},
            {'type': 'go_checkout'},
            {'type': 'open_contact'},
        ]

        respuesta = contrato.validar_respuesta(self.datos)

        self.assertEqual([a.tipo for a in respuesta.acciones], ['add_to_cart', 'go_checkout', 'open_contact'])
        self.assertEqual(respuesta.descartadas, 2)

    def test_acciones_malformadas_se_descartan_sin_invalidar_la_respuesta(self):
        self.datos['ui_actions'] = [
            'add_to_cart',
            {'type': 'add_to_cart'},
            {'type': 'add_to_cart', 'variant_id': '31'},
            {'type': 'add_to_cart', 'variant_id': True},
            {'type': 'add_to_cart', 'variant_id': 31.5},
            {'type': 'open_product'},
        ]

        respuesta = contrato.validar_respuesta(self.datos)

        self.assertEqual(respuesta.acciones, ())
        self.assertEqual(respuesta.descartadas, 6)

    def test_tope_de_acciones_y_tarjetas(self):
        self.datos['ui_actions'] = [{'type': 'go_checkout'}] * (contrato.MAX_ACCIONES + 3)
        self.datos['product_cards'] = [{'product_id': 1, 'reason': 'x'}] * (contrato.MAX_TARJETAS + 2)

        respuesta = contrato.validar_respuesta(self.datos)

        self.assertEqual(len(respuesta.acciones), contrato.MAX_ACCIONES)
        self.assertEqual(len(respuesta.tarjetas), contrato.MAX_TARJETAS)
        self.assertEqual(respuesta.descartadas, 5)

    def test_una_etiqueta_demasiado_larga_se_ignora(self):
        self.datos['ui_actions'] = [{'type': 'go_checkout', 'label': 'x' * 500}]

        respuesta = contrato.validar_respuesta(self.datos)

        self.assertEqual(respuesta.acciones[0].etiqueta, '')

    def test_respuesta_vacia_o_demasiado_larga_se_rechaza(self):
        for texto in ('', '  ', None, 5, 'x' * (contrato.MAX_LARGO_RESPUESTA + 1)):
            with self.subTest(texto=texto):
                self.datos['reply'] = texto
                with self.assertRaises(contrato.ContratoInvalido):
                    contrato.validar_respuesta(self.datos)

    def test_estructuras_inutilizables(self):
        casos = {
            'no es objeto': [],
            'sin meta': {'reply': 'hola'},
            'estado desconocido': {'reply': 'hola', 'meta': {'status': 'quiza'}},
            'reintento negativo': {'reply': 'hola', 'meta': {'status': 'ok', 'retry_after_seconds': -1}},
            'reintento enorme': {'reply': 'hola', 'meta': {'status': 'ok', 'retry_after_seconds': 99999}},
            'acciones no es lista': {'reply': 'hola', 'meta': {'status': 'ok'}, 'ui_actions': 'x'},
            'handoff no es objeto': {'reply': 'hola', 'meta': {'status': 'ok'}, 'handoff': 'persona'},
        }
        for nombre, datos in casos.items():
            with self.subTest(nombre), self.assertRaises(contrato.ContratoInvalido):
                contrato.validar_respuesta(datos)

    def test_campos_desconocidos_se_ignoran(self):
        self.datos['campo_nuevo'] = {'algo': 1}
        self.datos['meta']['otro'] = True

        respuesta = contrato.validar_respuesta(self.datos)

        self.assertTrue(respuesta.ok)

    def test_el_traspaso_conserva_solo_categoria_y_motivo(self):
        self.datos['handoff'] = {'category': 'queja', 'reason': 'Pidió hablar con una persona', 'extra': 'x'}

        respuesta = contrato.validar_respuesta(self.datos)

        self.assertEqual(respuesta.handoff, {'category': 'queja', 'reason': 'Pidió hablar con una persona'})

    def test_tarjeta_con_razon_demasiado_larga_se_descarta(self):
        self.datos['product_cards'] = [{'product_id': 12, 'reason': 'r' * (contrato.MAX_LARGO_RAZON + 1)}]

        respuesta = contrato.validar_respuesta(self.datos)

        self.assertEqual(respuesta.tarjetas, ())
        self.assertEqual(respuesta.descartadas, 1)
