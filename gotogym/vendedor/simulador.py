"""Servidor que hace de Coach para probar la tienda de punta a punta.

Se comporta como debe hacerlo el servicio real: lee el cuerpo crudo, verifica
la firma y la ventana de tiempo, comprueba el contrato, responde de forma
idempotente por `request_id` y nunca registra el texto del mensaje. Sirve para
tres cosas: probar el cliente HTTP con red de verdad, ver los estados del panel
(error, espera, respuesta rechazada) y darle al equipo del Coach una
referencia ejecutable de lo que la tienda envia y espera.

No es un modelo de IA: sus respuestas salen de los candidatos del paquete.
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import coach_client, contrato, firma

RUTA = '/api/commerce/agent/message/'
MODOS = ('ok', 'error', 'malicioso', 'lento', 'caido')


def crear_servidor(host, puerto, clave_id, secreto, modo='ok', demora=20.0, registro=None):
    """`ThreadingHTTPServer` listo para `serve_forever()`.

    `modo`: `ok` responde con el Coach simulado; `error` devuelve un estado de
    error con espera; `malicioso` devuelve acciones que la tienda debe
    descartar; `lento` tarda `demora` segundos; `caido` responde 503.
    `registro` recibe una linea por peticion (sin texto de mensajes)."""
    if modo not in MODOS:
        raise ValueError(f'Modo desconocido: {modo}')
    anotar = registro or (lambda linea: None)
    respuestas_dadas = {}

    class Manejador(BaseHTTPRequestHandler):
        def _enviar(self, estado, cuerpo, repeticion=False):
            # Se anota antes de responder: quien recibe la respuesta ya puede
            # contar con que la linea del registro existe.
            anotar(f'POST {self.path} -> {estado}')
            datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode('utf-8')
            try:
                self.send_response(estado)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(datos)))
                if repeticion:
                    self.send_header('X-Idempotent-Replay', 'true')
                self.end_headers()
                self.wfile.write(datos)
            except OSError:
                pass  # el cliente se fue (por ejemplo, por tiempo de espera)
            return estado

        def do_POST(self):
            self._atender()

        def _atender(self):
            if self.path != RUTA:
                return self._enviar(404, {'error': 'ruta'})
            try:
                largo = int(self.headers.get('Content-Length') or 0)
            except ValueError:
                return self._enviar(400, {'error': 'largo'})
            if largo > contrato.MAX_BYTES_SOLICITUD * 2:
                return self._enviar(413, {'error': 'tamano'})
            cuerpo = self.rfile.read(largo)

            if self.headers.get(firma.ENCABEZADO_CLAVE) != clave_id:
                return self._enviar(401, {'error': 'clave'})
            try:
                firma.verificar(
                    secreto, self.headers.get(firma.ENCABEZADO_MARCA),
                    cuerpo, self.headers.get(firma.ENCABEZADO_FIRMA),
                )
            except firma.FirmaInvalida as error:
                return self._enviar(401, {'error': error.motivo})
            if self.headers.get(firma.ENCABEZADO_CONTRATO) != contrato.VERSION_CONTRATO:
                return self._enviar(400, {'error': 'version_del_contrato'})

            try:
                solicitud = json.loads(cuerpo)
                contrato.validar_solicitud(solicitud)
            except ValueError as error:
                # ContratoInvalido es un ValueError: nombra el campo, no el valor.
                campo = str(error) if isinstance(error, contrato.ContratoInvalido) else 'json'
                return self._enviar(422, {'error': 'contrato', 'campo': campo})

            id_solicitud = solicitud['request_id']
            if id_solicitud in respuestas_dadas:
                estado_previo, cuerpo_previo = respuestas_dadas[id_solicitud]
                return self._enviar(estado_previo, cuerpo_previo, repeticion=True)

            estado, respuesta = self._respuesta(solicitud)
            datos = json.dumps(respuesta, ensure_ascii=False).encode('utf-8')
            respuestas_dadas[id_solicitud] = (estado, datos)
            return self._enviar(estado, datos)

        def _respuesta(self, solicitud):
            if modo == 'caido':
                return 503, {'error': 'servicio'}
            if modo == 'lento':
                time.sleep(demora)
            if modo == 'error':
                return 200, {
                    'reply': '', 'ui_actions': [], 'product_cards': [], 'handoff': None,
                    'meta': {'status': 'error', 'agents_used': [], 'evidence_refs': [], 'retry_after_seconds': 5},
                }
            if modo == 'malicioso':
                return 200, coach_client.respuesta_maliciosa_simulada()
            return 200, coach_client.respuesta_simulada(solicitud)

        def log_message(self, *args):
            pass

    servidor = ThreadingHTTPServer((host, puerto), Manejador)
    servidor.daemon_threads = True
    return servidor
