"""Coach simulado: se comporta como el servicio real y sirve de referencia."""
import json
import os
import threading
import time
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import mock

import requests
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from . import coach_client, contrato, firma, simulador
from .test_utilidades import aislar_catalogo, crear_producto

CLAVE = 'clave-simulador'
SECRETO = 'secreto-simulador'
EJEMPLOS = Path(__file__).resolve().parent / 'ejemplos'
NO_PROXY = {'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'}


def _solicitud():
    return json.loads((EJEMPLOS / 'solicitud.json').read_text(encoding='utf-8'))


class _Simulado:
    def __init__(self, modo='ok', demora=20.0):
        self.lineas = []
        self.servidor = simulador.crear_servidor(
            '127.0.0.1', 0, CLAVE, SECRETO, modo=modo, demora=demora, registro=self.lineas.append,
        )
        self.url = f'http://127.0.0.1:{self.servidor.server_address[1]}{simulador.RUTA}'
        self._hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self._hilo.start()

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def cliente(self, timeout=5.0, secreto=SECRETO):
        return coach_client.ClienteHttp(self.url, CLAVE, secreto, timeout)

    def post(self, solicitud=None, cuerpo=None, ahora=None, version='1', clave=CLAVE, secreto=SECRETO, url=None):
        datos = cuerpo if cuerpo is not None else contrato.serializar(solicitud or _solicitud())
        cabeceras = firma.encabezados_firmados(clave, secreto, datos, ahora=ahora)
        if version is not None:
            cabeceras[firma.ENCABEZADO_CONTRATO] = version
        return requests.post(url or self.url, data=datos, headers=cabeceras, timeout=5)


@mock.patch.dict(os.environ, NO_PROXY)
class SimuladorTests(SimpleTestCase):
    def _simulado(self, **kwargs):
        simulado = _Simulado(**kwargs)
        self.addCleanup(simulado.cerrar)
        return simulado

    def test_responde_a_una_solicitud_firmada_del_cliente_real(self):
        respuesta = self._simulado().cliente().enviar(_solicitud())

        self.assertTrue(respuesta.ok)
        self.assertIn('simulada', respuesta.texto)
        self.assertEqual(respuesta.acciones[0].tipo, 'open_product')

    def test_rechaza_una_firma_con_otro_secreto(self):
        respuesta = self._simulado().post(secreto='otro')

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()['error'], 'no_coincide')

    def test_rechaza_una_solicitud_expirada(self):
        respuesta = self._simulado().post(ahora=time.time() - 3600)

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json()['error'], 'expirada')

    def test_rechaza_una_clave_desconocida(self):
        respuesta = self._simulado().post(clave='intrusa')

        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (401, 'clave'))

    def test_rechaza_una_solicitud_sin_firma(self):
        respuesta = requests.post(self._simulado().url, data=b'{}', timeout=5)

        self.assertEqual(respuesta.status_code, 401)

    def test_rechaza_otra_version_del_contrato(self):
        simulado = self._simulado()

        self.assertEqual(simulado.post(version='2').status_code, 400)
        self.assertEqual(simulado.post(version=None).status_code, 400)

    def test_rechaza_un_cuerpo_fuera_de_contrato_nombrando_el_campo(self):
        solicitud = _solicitud()
        solicitud['cart']['subtotal'] = 400000.0

        respuesta = self._simulado().post(solicitud)

        self.assertEqual(respuesta.status_code, 422)
        self.assertEqual(respuesta.json(), {'error': 'contrato', 'campo': 'cart.subtotal'})

    def test_rechaza_datos_personales(self):
        solicitud = _solicitud()
        solicitud['visitor']['email'] = 'ana@example.com'

        respuesta = self._simulado().post(solicitud)

        self.assertEqual(respuesta.status_code, 422)
        self.assertNotIn('ana@example.com', respuesta.text)

    def test_json_ilegible(self):
        respuesta = self._simulado().post(cuerpo=b'no es json')

        self.assertEqual(respuesta.status_code, 422)

    def test_ruta_desconocida_y_cuerpo_enorme(self):
        simulado = self._simulado()

        self.assertEqual(simulado.post(url=simulado.url.replace('commerce', 'otra')).status_code, 404)
        self.assertEqual(simulado.post(cuerpo=b'x' * (contrato.MAX_BYTES_SOLICITUD * 2 + 10)).status_code, 413)

    def test_repetir_el_request_id_devuelve_la_misma_respuesta(self):
        simulado = self._simulado()
        solicitud = _solicitud()

        primera = simulado.post(solicitud)
        segunda = simulado.post(solicitud)

        self.assertEqual(primera.content, segunda.content)
        self.assertNotIn('X-Idempotent-Replay', primera.headers)
        self.assertEqual(segunda.headers['X-Idempotent-Replay'], 'true')

    def test_un_request_id_nuevo_se_procesa_de_nuevo(self):
        simulado = self._simulado()
        solicitud = _solicitud()
        simulado.post(solicitud)
        solicitud['request_id'] = 'otro-turno'

        self.assertNotIn('X-Idempotent-Replay', simulado.post(solicitud).headers)

    def test_no_registra_el_texto_del_mensaje(self):
        simulado = self._simulado()
        solicitud = _solicitud()
        solicitud['message'] = 'TEXTO-PRIVADO-DEL-VISITANTE'

        simulado.post(solicitud)

        self.assertTrue(simulado.lineas)
        self.assertFalse(any('PRIVADO' in linea for linea in simulado.lineas))

    def test_modo_error_devuelve_estado_error_con_espera(self):
        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._simulado(modo='error').cliente().enviar(_solicitud())

        self.assertEqual((ctx.exception.codigo, ctx.exception.reintentar_en), ('error_del_coach', 5))

    def test_modo_caido_responde_503(self):
        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._simulado(modo='caido').cliente().enviar(_solicitud())

        self.assertEqual(ctx.exception.codigo, 'servicio')

    def test_modo_lento_provoca_timeout(self):
        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._simulado(modo='lento', demora=1.5).cliente(timeout=0.3).enviar(_solicitud())

        self.assertEqual(ctx.exception.codigo, 'timeout')

    def test_modo_malicioso_llega_al_contrato_ya_recortado(self):
        respuesta = self._simulado(modo='malicioso').cliente().enviar(_solicitud())

        self.assertNotIn('apply_coupon', [a.tipo for a in respuesta.acciones])
        self.assertGreaterEqual(respuesta.descartadas, 1)

    def test_modo_desconocido(self):
        with self.assertRaises(ValueError):
            simulador.crear_servidor('127.0.0.1', 0, CLAVE, SECRETO, modo='raro')


@mock.patch.dict(os.environ, NO_PROXY)
class DeExtremoAExtremoTests(TestCase):
    """Navegador -> vista del puente -> cliente HTTP firmado -> Coach simulado."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        aislar_catalogo()
        self.producto, (self.variante,) = crear_producto(
            'Leggins Quantum', [('M', 'gris', 5, {'price_override': Decimal('400000.0000')})],
        )

    def _mensaje(self, mensaje='Busco leggins'):
        return self.client.post(
            '/es/vendedor/mensaje/', data=json.dumps({'message': mensaje}),
            content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def _contra(self, modo='ok', secreto=SECRETO, **extra):
        simulado = _Simulado(modo=modo, **extra)
        self.addCleanup(simulado.cerrar)
        return override_settings(
            VENDEDOR_ENABLED=True, COACH_API_URL=simulado.url, COACH_SERVICE_KEY_ID=CLAVE,
            COACH_SERVICE_SECRET=secreto, VENDEDOR_COACH_SIMULADO=False,
        )

    def test_el_recorrido_completo_funciona(self):
        with self._contra():
            respuesta = self._mensaje()

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo['ok'])
        self.assertEqual(cuerpo['cards'][0]['name'], 'Leggins Quantum')
        self.assertEqual(cuerpo['cards'][0]['price'], '$400.000 COP')
        agregar = next(a for a in cuerpo['actions'] if a['type'] == 'add_to_cart')
        self.assertEqual(agregar['endpoint'], f'/es/carrito/add/{self.variante.id}/')

    def test_con_la_clave_equivocada_el_panel_ve_un_error_y_no_una_respuesta(self):
        # El simulador usa SECRETO; la tienda se configura con otro.
        with self._contra(secreto='distinto-al-del-simulador'):
            respuesta = self._mensaje()

        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(respuesta.json()['error'], 'error')
        self.assertNotIn('reply', respuesta.json())

    def test_el_coach_malicioso_no_logra_nada(self):
        with self._contra(modo='malicioso'):
            respuesta = self._mensaje()

        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(respuesta.json()['error'], 'respuesta_rechazada')

    def test_el_coach_en_modo_error_hace_esperar(self):
        with self._contra(modo='error'):
            primera = self._mensaje()
            segunda = self._mensaje()

        self.assertEqual(primera.json()['retry_after'], 5)
        self.assertEqual(segunda.status_code, 429)
        self.assertEqual(segunda.json()['error'], 'espera')

    def test_el_coach_caido_abre_el_circuito(self):
        with self._contra(modo='caido'):
            for _ in range(coach_client.FALLOS_PARA_ABRIR):
                self._mensaje()
            respuesta = self._mensaje()

        self.assertEqual(respuesta.json()['error'], 'no_disponible')


class ComandoTests(SimpleTestCase):
    def test_sin_clave_ni_secreto_avisa(self):
        with override_settings(COACH_SERVICE_KEY_ID='', COACH_SERVICE_SECRET=''), \
                self.assertRaisesMessage(CommandError, 'Faltan COACH_SERVICE_KEY_ID'):
            call_command('vendedor_simular_coach', stdout=StringIO())

    def test_el_comando_arranca_el_servidor_con_lo_indicado(self):
        servidor = mock.Mock()
        servidor.serve_forever.side_effect = KeyboardInterrupt
        salida = StringIO()

        with mock.patch.object(simulador, 'crear_servidor', return_value=servidor) as crear:
            call_command('vendedor_simular_coach', '--port', '8765', '--modo', 'error',
                         '--clave-id', 'k', '--secreto', 's', stdout=salida)

        crear.assert_called_once()
        argumentos = crear.call_args
        self.assertEqual(argumentos.args[:4], ('127.0.0.1', 8765, 'k', 's'))
        self.assertEqual(argumentos.kwargs['modo'], 'error')
        servidor.server_close.assert_called_once()
        self.assertIn('Coach simulado (error)', salida.getvalue())

    def test_el_puerto_por_defecto_deja_libre_el_8001(self):
        servidor = mock.Mock()
        servidor.serve_forever.side_effect = KeyboardInterrupt

        with mock.patch.object(simulador, 'crear_servidor', return_value=servidor) as crear:
            call_command('vendedor_simular_coach', '--clave-id', 'k', '--secreto', 's', stdout=StringIO())

        self.assertEqual(crear.call_args.args[1], 8002)
