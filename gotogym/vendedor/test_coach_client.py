"""Clientes del Coach: el real (contra un servidor local que verifica la firma),
el simulado y el circuito de corte."""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from . import coach_client, contrato, firma

EJEMPLOS = Path(__file__).resolve().parent / 'ejemplos'
SECRETO = 'secreto-de-prueba'
CLAVE = 'clave-de-prueba'


def _ejemplo(nombre):
    return json.loads((EJEMPLOS / nombre).read_text(encoding='utf-8'))


class _Servidor:
    """Servidor HTTP local que hace de Coach. Guarda lo que recibe y responde
    lo que se le indique (`estado`, `cuerpo`, `cabeceras`, `demora`)."""

    def __init__(self, estado=200, cuerpo=None, cabeceras=None, demora=0):
        self.estado = estado
        self.cuerpo = json.dumps(_ejemplo('respuesta_ok.json')).encode() if cuerpo is None else cuerpo
        self.cabeceras = cabeceras or {}
        self.demora = demora
        self.recibidas = []
        servidor = self

        class Manejador(BaseHTTPRequestHandler):
            def do_POST(self):
                largo = int(self.headers.get('Content-Length', 0))
                servidor.recibidas.append({
                    'cabeceras': {k: v for k, v in self.headers.items()},
                    'cuerpo': self.rfile.read(largo),
                    'ruta': self.path,
                })
                if servidor.demora:
                    time.sleep(servidor.demora)
                try:
                    self.send_response(servidor.estado)
                    for nombre, valor in servidor.cabeceras.items():
                        self.send_header(nombre, valor)
                    self.send_header('Content-Length', str(len(servidor.cuerpo)))
                    self.end_headers()
                    self.wfile.write(servidor.cuerpo)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        self._http = ThreadingHTTPServer(('127.0.0.1', 0), Manejador)
        self._http.daemon_threads = True
        self.url = f'http://127.0.0.1:{self._http.server_address[1]}/api/commerce/agent/message/'
        self._hilo = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._hilo.start()

    def cerrar(self):
        self._http.shutdown()
        self._http.server_close()


@mock.patch.dict(os.environ, {'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'})
class ClienteHttpTests(SimpleTestCase):
    def _servidor(self, **kwargs):
        servidor = _Servidor(**kwargs)
        self.addCleanup(servidor.cerrar)
        return servidor

    def _cliente(self, servidor, timeout=5.0, secreto=SECRETO, clave=CLAVE):
        return coach_client.ClienteHttp(servidor.url, clave, secreto, timeout)

    def _enviar(self, cliente):
        return cliente.enviar(_ejemplo('solicitud.json'))

    def test_la_solicitud_llega_firmada_y_el_receptor_la_verifica(self):
        servidor = self._servidor()

        respuesta = self._enviar(self._cliente(servidor))

        self.assertTrue(respuesta.ok)
        recibida = servidor.recibidas[0]
        cabeceras = {k.lower(): v for k, v in recibida['cabeceras'].items()}
        self.assertEqual(cabeceras['x-coach-key-id'], CLAVE)
        self.assertEqual(cabeceras['x-vendedor-contract'], contrato.VERSION_CONTRATO)
        self.assertTrue(cabeceras['content-type'].startswith('application/json'))
        # Lo que hace el Coach: verificar con el cuerpo crudo y la marca recibida.
        firma.verificar(
            SECRETO, cabeceras['x-coach-timestamp'], recibida['cuerpo'], cabeceras['x-coach-signature'],
        )
        self.assertEqual(json.loads(recibida['cuerpo']), _ejemplo('solicitud.json'))

    def test_con_otro_secreto_el_receptor_rechaza_la_firma(self):
        servidor = self._servidor()
        self._enviar(self._cliente(servidor))
        recibida = servidor.recibidas[0]
        cabeceras = {k.lower(): v for k, v in recibida['cabeceras'].items()}

        with self.assertRaises(firma.FirmaInvalida):
            firma.verificar(
                'otro-secreto', cabeceras['x-coach-timestamp'], recibida['cuerpo'],
                cabeceras['x-coach-signature'],
            )

    def test_la_respuesta_ok_se_convierte_en_respuesta_del_coach(self):
        servidor = self._servidor()

        respuesta = self._enviar(self._cliente(servidor))

        self.assertEqual([a.tipo for a in respuesta.acciones], ['add_to_cart', 'open_product'])

    def test_errores_http_se_clasifican(self):
        casos = [
            (500, 'servicio'), (502, 'servicio'), (503, 'servicio'),
            (400, 'rechazado'), (401, 'rechazado'), (403, 'rechazado'), (404, 'rechazado'),
            (204, 'rechazado'),
        ]
        for estado, codigo in casos:
            with self.subTest(estado=estado):
                servidor = self._servidor(estado=estado, cuerpo=b'{}')
                with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
                    self._enviar(self._cliente(servidor))
                self.assertEqual(ctx.exception.codigo, codigo)

    def test_un_rechazo_conserva_el_estado_y_el_codigo_del_coach(self):
        casos = [
            (400, b'{"error": "invalid_promotion"}', 'http_400:invalid_promotion'),
            (401, b'{"error": "unauthorized"}', 'http_401:unauthorized'),
            # Texto libre o sin JSON: solo el estado, nunca el contenido.
            (400, b'{"error": "Algo salio mal con el usuario x"}', 'http_400'),
            (403, b'<html>prohibido</html>', 'http_403'),
            (503, b'{}', 'http_503'),
        ]
        for estado, cuerpo, detalle in casos:
            with self.subTest(estado=estado, cuerpo=cuerpo):
                servidor = self._servidor(estado=estado, cuerpo=cuerpo)
                with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
                    self._enviar(self._cliente(servidor))
                self.assertEqual(ctx.exception.detalle, detalle)

    def test_un_429_del_coach_respeta_su_espera(self):
        servidor = self._servidor(estado=429, cuerpo=b'{}', cabeceras={'Retry-After': '7'})

        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._enviar(self._cliente(servidor))

        self.assertEqual(ctx.exception.codigo, 'limite')
        self.assertEqual(ctx.exception.reintentar_en, 7)

    def test_una_espera_absurda_se_acota_y_una_ilegible_se_ignora(self):
        for cabecera, esperado in (('999999', coach_client.MAX_RETRY_AFTER), ('mañana', None), ('-5', 0)):
            with self.subTest(cabecera=cabecera):
                servidor = self._servidor(estado=429, cuerpo=b'{}', cabeceras={'Retry-After': cabecera})
                with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
                    self._enviar(self._cliente(servidor))
                self.assertEqual(ctx.exception.reintentar_en, esperado)

    def test_no_sigue_redirecciones(self):
        destino = self._servidor()
        servidor = self._servidor(estado=302, cuerpo=b'', cabeceras={'Location': destino.url})

        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._enviar(self._cliente(servidor))

        self.assertEqual(ctx.exception.codigo, 'rechazado')
        self.assertEqual(destino.recibidas, [])

    def test_json_ilegible_o_fuera_de_contrato(self):
        casos = {
            'no es json': b'<html>error</html>',
            'no es objeto': b'[]',
            'sin meta': b'{"reply": "hola"}',
            'sin texto': json.dumps({'meta': {'status': 'ok'}}).encode(),
        }
        for nombre, cuerpo in casos.items():
            with self.subTest(nombre):
                servidor = self._servidor(cuerpo=cuerpo)
                with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
                    self._enviar(self._cliente(servidor))
                self.assertEqual(ctx.exception.codigo, 'respuesta_invalida')

    def test_estado_error_del_coach_trae_su_espera(self):
        servidor = self._servidor(cuerpo=json.dumps(_ejemplo('respuesta_error.json')).encode())

        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._enviar(self._cliente(servidor))

        self.assertEqual(ctx.exception.codigo, 'error_del_coach')
        self.assertEqual(ctx.exception.reintentar_en, 20)

    def test_si_tarda_demasiado_es_un_timeout(self):
        servidor = self._servidor(demora=1.5)

        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._enviar(self._cliente(servidor, timeout=0.3))

        self.assertEqual(ctx.exception.codigo, 'timeout')

    def test_sin_nadie_escuchando_es_un_fallo_de_conexion(self):
        servidor = _Servidor()
        url = servidor.url
        servidor.cerrar()

        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            coach_client.ClienteHttp(url, CLAVE, SECRETO, 2.0).enviar(_ejemplo('solicitud.json'))

        self.assertEqual(ctx.exception.codigo, 'conexion')

    def test_sin_secreto_o_sin_clave_no_se_envia_nada(self):
        servidor = self._servidor()
        for secreto, clave in (('', CLAVE), (SECRETO, '')):
            with self.subTest(secreto=bool(secreto), clave=bool(clave)):
                with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
                    self._enviar(self._cliente(servidor, secreto=secreto, clave=clave))
                self.assertEqual(ctx.exception.codigo, 'no_configurado')
        self.assertEqual(servidor.recibidas, [])

    def test_no_se_envia_nada_a_una_url_http_remota(self):
        cliente = coach_client.ClienteHttp('http://coach.example.com/api/', CLAVE, SECRETO, 2.0)

        with mock.patch.object(coach_client.requests, 'post') as post, \
                self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._enviar(cliente)

        self.assertEqual(ctx.exception.codigo, 'no_configurado')
        post.assert_not_called()

    def test_urls_permitidas(self):
        permitidas = ['https://api.gotogym.store/x', 'http://localhost:8001/x', 'http://127.0.0.1:8001/x']
        rechazadas = ['http://api.gotogym.store/x', 'ftp://x', 'api.gotogym.store', '', 'https://']
        for url in permitidas:
            self.assertTrue(coach_client._url_permitida(url), url)
        for url in rechazadas:
            self.assertFalse(coach_client._url_permitida(url), url)

    def test_los_errores_no_incluyen_el_texto_del_visitante(self):
        servidor = self._servidor(estado=500)
        solicitud = _ejemplo('solicitud.json')
        solicitud['message'] = 'TEXTO-PRIVADO-DEL-VISITANTE'

        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            self._cliente(servidor).enviar(solicitud)

        self.assertNotIn('PRIVADO', str(ctx.exception))
        self.assertNotIn('PRIVADO', repr(ctx.exception.__dict__))


class ClienteSimuladoTests(SimpleTestCase):
    def _solicitud(self, mensaje='hola', **cambios):
        solicitud = _ejemplo('solicitud.json')
        solicitud['message'] = mensaje
        solicitud.update(cambios)
        return solicitud

    def test_responde_con_lo_que_hay_en_el_paquete_y_lo_dice(self):
        respuesta = coach_client.ClienteSimulado().enviar(self._solicitud())

        self.assertIn('simulada', respuesta.texto)
        self.assertIn('Leggins Quantum', respuesta.texto)
        tipos = [a.tipo for a in respuesta.acciones]
        self.assertEqual(tipos[:2], ['open_product', 'add_to_cart'])
        self.assertIn('go_checkout', tipos)  # el ejemplo trae un producto en el carrito
        self.assertEqual(respuesta.meta.agentes, ('simulado',))

    def test_la_variante_propuesta_tiene_existencias(self):
        solicitud = self._solicitud()
        solicitud['evidence']['candidates'][0]['variants'][0]['available'] = 0

        respuesta = coach_client.ClienteSimulado().enviar(solicitud)

        agregar = next(a for a in respuesta.acciones if a.tipo == 'add_to_cart')
        self.assertEqual(agregar.variant_id, 31)

    def test_con_las_compras_en_pausa_no_propone_agregar(self):
        solicitud = self._solicitud()
        solicitud['shop_flags']['purchases_paused'] = True

        respuesta = coach_client.ClienteSimulado().enviar(solicitud)

        self.assertNotIn('add_to_cart', [a.tipo for a in respuesta.acciones])

    def test_sin_candidatos_lo_dice(self):
        solicitud = self._solicitud()
        solicitud['evidence']['candidates'] = []

        respuesta = coach_client.ClienteSimulado().enviar(solicitud)

        self.assertEqual(respuesta.acciones, ())
        self.assertIn('No tengo productos', respuesta.texto)

    def test_mensaje_de_prueba_para_el_error(self):
        with self.assertRaises(coach_client.CoachNoDisponible) as ctx:
            coach_client.ClienteSimulado().enviar(self._solicitud(coach_client.PALABRA_ERROR_SIMULADO))

        self.assertEqual(ctx.exception.codigo, 'error_del_coach')
        self.assertEqual(ctx.exception.reintentar_en, 5)

    def test_mensaje_de_prueba_malicioso_pasa_por_el_mismo_contrato(self):
        respuesta = coach_client.ClienteSimulado().enviar(
            self._solicitud(coach_client.PALABRA_MALICIOSO_SIMULADO)
        )

        # `apply_coupon` queda fuera de la lista blanca ya en el contrato.
        self.assertNotIn('apply_coupon', [a.tipo for a in respuesta.acciones])
        self.assertGreaterEqual(respuesta.descartadas, 1)


class SeleccionDeClienteTests(SimpleTestCase):
    def test_con_url_se_usa_el_cliente_real(self):
        with override_settings(COACH_API_URL='http://127.0.0.1:8001/x', VENDEDOR_COACH_SIMULADO=True):
            self.assertIsInstance(coach_client.obtener_cliente(), coach_client.ClienteHttp)

    def test_sin_url_y_con_simulacion_se_usa_el_simulado(self):
        with override_settings(COACH_API_URL='', VENDEDOR_COACH_SIMULADO=True):
            self.assertIsInstance(coach_client.obtener_cliente(), coach_client.ClienteSimulado)

    def test_sin_url_y_sin_simulacion_no_hay_cliente(self):
        with override_settings(COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False):
            self.assertIsNone(coach_client.obtener_cliente())

    def _simulado_por_defecto(self, **entorno):
        """Valor de `VENDEDOR_COACH_SIMULADO` que sale de importar la
        configuracion en un proceso aparte con el entorno indicado."""
        base = {
            'PATH': os.environ.get('PATH', ''),
            'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''),
            'PYTHONUTF8': '1',
            'DJANGO_SECRET_KEY': 'clave-de-prueba',
        }
        resultado = subprocess.run(
            [sys.executable, '-c', 'import gotogym.settings as s; print(s.VENDEDOR_COACH_SIMULADO)'],
            cwd=settings.BASE_DIR, env={**base, **entorno}, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        return resultado.stdout.strip().splitlines()[-1] == 'True'

    def test_la_simulacion_esta_apagada_por_defecto_en_produccion(self):
        # Un cliente real nunca debe recibir una respuesta simulada.
        self.assertFalse(self._simulado_por_defecto())

    def test_la_simulacion_esta_activa_por_defecto_en_desarrollo(self):
        self.assertTrue(self._simulado_por_defecto(DEBUG='true'))

    def test_la_simulacion_se_puede_apagar_expresamente_en_desarrollo(self):
        self.assertFalse(self._simulado_por_defecto(DEBUG='true', VENDEDOR_COACH_SIMULADO='false'))


class CircuitoTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        # Reloj fijo: los fallos se cuentan por ventana de reloj y una prueba
        # que cruzara el cambio de minuto se partiria en dos ventanas.
        reloj = mock.patch('gotogym.ratelimit._ahora', return_value=1_000_020.0)
        reloj.start()
        self.addCleanup(reloj.stop)

    def test_empieza_cerrado(self):
        self.assertFalse(coach_client.circuito_abierto())

    def test_se_abre_tras_los_fallos_seguidos(self):
        for _ in range(coach_client.FALLOS_PARA_ABRIR - 1):
            coach_client.registrar_fallo()
        self.assertFalse(coach_client.circuito_abierto())

        coach_client.registrar_fallo()

        self.assertTrue(coach_client.circuito_abierto())

    def test_un_exito_reinicia_la_cuenta(self):
        for _ in range(coach_client.FALLOS_PARA_ABRIR - 1):
            coach_client.registrar_fallo()
        coach_client.registrar_exito()
        coach_client.registrar_fallo()

        self.assertFalse(coach_client.circuito_abierto())

    def test_abrirse_se_registra_una_sola_vez(self):
        with self.assertLogs('vendedor.coach_client', level='ERROR') as registros:
            for _ in range(coach_client.FALLOS_PARA_ABRIR + 3):
                coach_client.registrar_fallo()

        self.assertEqual(len(registros.records), 1)
