"""Contrato de vision tienda -> Coach y su cliente HTTP."""
import base64
import json
import threading
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import coach_client, contrato, firma, imagen, simulador, vision
from .test_imagen import foto

EJEMPLOS = Path(__file__).resolve().parent / 'ejemplos'


def _ejemplo(nombre):
    return json.loads((EJEMPLOS / nombre).read_text(encoding='utf-8'))


def _respuesta_http(estado=200, cuerpo=None):
    respuesta = mock.Mock(status_code=estado, headers={})
    respuesta.json.return_value = cuerpo if cuerpo is not None else _ejemplo('vision_respuesta_ok.json')
    return respuesta


class SolicitudTests(SimpleTestCase):
    def test_lleva_la_foto_preparada_y_el_vocabulario(self):
        preparada = imagen.preparar(foto())

        solicitud = vision.armar_solicitud(preparada, 'en', request_id='r-1', ahora=1000)

        self.assertEqual(solicitud['purpose'], 'similar_products')
        self.assertEqual(solicitud['locale'], 'en')
        self.assertEqual(solicitud['timestamp'], 1000)
        self.assertEqual(base64.b64decode(solicitud['image']['data']), preparada.datos)
        self.assertEqual(solicitud['vocabulary']['version'], 'v1')
        self.assertLessEqual(len(vision.serializar(solicitud)), vision.MAX_BYTES_SOLICITUD)

    def test_el_ejemplo_tiene_la_misma_forma(self):
        ejemplo = _ejemplo('vision_solicitud.json')
        armada = vision.armar_solicitud(imagen.preparar(foto()), 'es')

        self.assertEqual(set(ejemplo), set(armada))
        self.assertEqual(set(ejemplo['image']), set(armada['image']))
        self.assertEqual(ejemplo['vocabulary'], armada['vocabulary'])

    def test_rechaza_proposito_o_idioma_desconocidos(self):
        preparada = imagen.preparar(foto())
        with self.assertRaises(contrato.ContratoInvalido):
            vision.armar_solicitud(preparada, 'es', proposito='otra_cosa')
        with self.assertRaises(contrato.ContratoInvalido):
            vision.armar_solicitud(preparada, 'pt')


class RespuestaTests(SimpleTestCase):
    def test_el_ejemplo_es_valido(self):
        descripcion = vision.validar_respuesta(_ejemplo('vision_respuesta_ok.json'))

        self.assertTrue(descripcion.ok and descripcion.prenda)
        self.assertEqual(descripcion.atributos['garment_type'], 'leggings')
        self.assertEqual(descripcion.confianza, 0.82)

    def test_atributos_fuera_del_vocabulario_se_descartan(self):
        datos = _ejemplo('vision_respuesta_ok.json')
        datos['attributes'] = {'garment_type': 'kimono', 'colors': ['gris', 'plateado'], 'face': 'sonriente'}

        self.assertEqual(vision.validar_respuesta(datos).atributos, {'colors': ['gris']})

    def test_sin_prenda_no_quedan_atributos(self):
        datos = _ejemplo('vision_respuesta_ok.json')
        datos['garment_detected'] = False

        self.assertEqual(vision.validar_respuesta(datos).atributos, {})

    def test_error_del_coach(self):
        descripcion = vision.validar_respuesta(
            {'meta': {'status': 'error', 'error_code': 'image_rejected', 'retry_after_seconds': 5}})

        self.assertFalse(descripcion.ok)
        self.assertEqual((descripcion.codigo_error, descripcion.reintentar_en), ('image_rejected', 5))

    def test_forma_invalida(self):
        base = _ejemplo('vision_respuesta_ok.json')
        malas = [
            [],
            {'meta': 'ok'},
            {**base, 'meta': {'status': 'quiza'}},
            {**base, 'garment_detected': 'si'},
            {**base, 'person_present': None},
            {**base, 'confidence': 3},
            {**base, 'confidence': True},
            {'meta': {'status': 'error', 'retry_after_seconds': -1}},
        ]
        for datos in malas:
            with self.subTest(datos=datos), self.assertRaises(contrato.ContratoInvalido):
                vision.validar_respuesta(datos)


class UrlDeVisionTests(SimpleTestCase):
    def test_se_deriva_de_la_url_del_turno(self):
        self.assertEqual(
            coach_client.url_de_vision('https://api.example/api/commerce/agent/message/', ''),
            'https://api.example/api/commerce/vision/describe/')

    def test_la_configurada_manda(self):
        self.assertEqual(coach_client.url_de_vision('https://a/x/', 'https://b/v/'), 'https://b/v/')

    def test_sin_forma_conocida_no_se_adivina(self):
        self.assertEqual(coach_client.url_de_vision('https://api.example/otra/', ''), '')


class ClienteHttpVisionTests(SimpleTestCase):
    def setUp(self):
        self.cliente = coach_client.ClienteHttp(
            'https://coach.example/api/commerce/agent/message/', 'clave', 'secreto', 5,
            url_vision='https://coach.example/api/commerce/vision/describe/')
        self.solicitud = vision.armar_solicitud(imagen.preparar(foto()), 'es')

    def test_firma_y_declara_el_contrato_de_vision(self):
        with mock.patch.object(coach_client.requests, 'post', return_value=_respuesta_http()) as post:
            descripcion = self.cliente.describir(self.solicitud)

        self.assertEqual(descripcion.atributos['garment_type'], 'leggings')
        argumentos = post.call_args
        self.assertEqual(argumentos.args[0], 'https://coach.example/api/commerce/vision/describe/')
        cabeceras = argumentos.kwargs['headers']
        self.assertEqual(cabeceras[firma.ENCABEZADO_CONTRATO], 'vision-1')
        self.assertFalse(argumentos.kwargs['allow_redirects'])
        firma.verificar('secreto', cabeceras[firma.ENCABEZADO_MARCA], argumentos.kwargs['data'],
                        cabeceras[firma.ENCABEZADO_FIRMA])

    def test_un_404_es_vision_no_soportada(self):
        with mock.patch.object(coach_client.requests, 'post', return_value=_respuesta_http(404, {})), \
                self.assertRaises(coach_client.CoachNoDisponible) as error:
            self.cliente.describir(self.solicitud)
        self.assertEqual(error.exception.codigo, 'no_soportado')

    def test_sin_url_de_vision_no_llama(self):
        cliente = coach_client.ClienteHttp('https://coach.example/x/', 'c', 's', 5)
        with mock.patch.object(coach_client.requests, 'post') as post, \
                self.assertRaises(coach_client.CoachNoDisponible) as error:
            cliente.describir(self.solicitud)
        post.assert_not_called()
        self.assertEqual(error.exception.codigo, 'no_soportado')

    def test_error_del_coach_y_respuesta_fuera_de_contrato(self):
        error_coach = _respuesta_http(200, {'meta': {'status': 'error', 'error_code': 'image_rejected'}})
        with mock.patch.object(coach_client.requests, 'post', return_value=error_coach), \
                self.assertRaises(coach_client.CoachNoDisponible) as error:
            self.cliente.describir(self.solicitud)
        self.assertEqual((error.exception.codigo, error.exception.detalle), ('error_del_coach', 'image_rejected'))

        with mock.patch.object(coach_client.requests, 'post', return_value=_respuesta_http(200, {'meta': {}})), \
                self.assertRaises(coach_client.CoachNoDisponible) as error:
            self.cliente.describir(self.solicitud)
        self.assertEqual(error.exception.codigo, 'respuesta_invalida')

    @override_settings(COACH_API_URL='https://coach.example/api/commerce/agent/message/', COACH_VISION_URL='')
    def test_obtener_cliente_configura_la_vision(self):
        self.assertEqual(coach_client.obtener_cliente().url_vision,
                         'https://coach.example/api/commerce/vision/describe/')


class ClienteSimuladoVisionTests(SimpleTestCase):
    def test_describe_con_el_color_de_la_foto(self):
        solicitud = vision.armar_solicitud(imagen.preparar(foto(color=(200, 20, 20))), 'es')

        descripcion = coach_client.ClienteSimulado().describir(solicitud)

        self.assertTrue(descripcion.prenda)
        self.assertEqual(descripcion.atributos['colors'], ['rojo'])


@mock.patch.dict('os.environ', {'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'})
class SimuladorVisionTests(SimpleTestCase):
    """El simulador local atiende la ruta de vision con firma real."""

    def _cliente(self, modo='ok'):
        servidor = simulador.crear_servidor('127.0.0.1', 0, 'clave', 'secreto', modo=modo)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        base = f'http://127.0.0.1:{servidor.server_address[1]}'
        return coach_client.ClienteHttp(
            base + simulador.RUTA, 'clave', 'secreto', 5,
            url_vision=coach_client.url_de_vision(base + simulador.RUTA, ''))

    def test_describe_por_http(self):
        solicitud = vision.armar_solicitud(imagen.preparar(foto(color=(20, 160, 40))), 'es')

        descripcion = self._cliente().describir(solicitud)

        self.assertEqual(descripcion.atributos['colors'], ['verde'])

    def test_modo_error(self):
        solicitud = vision.armar_solicitud(imagen.preparar(foto()), 'es')
        with self.assertRaises(coach_client.CoachNoDisponible) as error:
            self._cliente('error').describir(solicitud)
        self.assertEqual(error.exception.detalle, 'image_rejected')
