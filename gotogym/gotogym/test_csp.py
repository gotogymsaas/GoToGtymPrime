"""Content-Security-Policy: cabecera, nonce por peticion, endpoint de reportes y
que ningun script en linea de las plantillas se quede sin nonce."""
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

REPORTE = 'Content-Security-Policy-Report-Only'
APLICADA = 'Content-Security-Policy'


def _nonce(respuesta):
    return re.search(r"'nonce-([^']+)'", respuesta[REPORTE]).group(1)


class CabeceraTests(TestCase):
    def setUp(self):
        self.url = reverse('commercial_login')  # tiene scripts en linea

    def test_por_defecto_solo_reporta(self):
        respuesta = self.client.get(self.url)
        self.assertIn(REPORTE, respuesta)
        self.assertNotIn(APLICADA, respuesta)

    def test_la_politica_es_la_del_sitio(self):
        politica = self.client.get(self.url)[REPORTE]
        for directiva in (
            "default-src 'self'", "style-src 'self' 'unsafe-inline'", "img-src 'self' data: blob: https:",
            "connect-src 'self'", "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'",
            "object-src 'none'", 'report-uri /csp-reporte/',
        ):
            self.assertIn(directiva, politica)
        self.assertRegex(politica, r"script-src 'self' 'nonce-[\w-]+'(;|$)")

    def test_el_nonce_cambia_en_cada_peticion_y_esta_en_el_html(self):
        primera = self.client.get(self.url)
        segunda = self.client.get(self.url)
        self.assertNotEqual(_nonce(primera), _nonce(segunda))
        self.assertContains(primera, f'<script nonce="{_nonce(primera)}"')
        self.assertNotContains(primera, _nonce(segunda))

    @override_settings(CSP_MODO='aplicar')
    def test_modo_aplicar_usa_la_cabecera_que_bloquea(self):
        respuesta = self.client.get(self.url)
        self.assertIn(APLICADA, respuesta)
        self.assertNotIn(REPORTE, respuesta)

    @override_settings(CSP_MODO='apagado')
    def test_modo_apagado_quita_la_cabecera(self):
        respuesta = self.client.get(self.url)
        self.assertNotIn(APLICADA, respuesta)
        self.assertNotIn(REPORTE, respuesta)
        self.assertEqual(respuesta.status_code, 200)

    def test_las_respuestas_de_error_tambien_la_llevan(self):
        self.assertIn(REPORTE, self.client.get('/no-existe-esta-ruta/'))


class ReporteTests(TestCase):
    url = '/csp-reporte/'

    def _enviar(self, cuerpo, cliente=None, tipo='application/csp-report', **extra):
        return (cliente or self.client).post(
            self.url, data=cuerpo if isinstance(cuerpo, (str, bytes)) else json.dumps(cuerpo),
            content_type=tipo, **extra,
        )

    def test_registra_directiva_uri_y_pagina_sin_query_string_ni_ip(self):
        reporte = {'csp-report': {
            'effective-directive': "script-src-elem 'self' 'nonce-secreto'",
            'blocked-uri': 'https://cdn.ejemplo.test/lib.js?token=abc123',
            'document-uri': 'https://gotogym.store/tienda/?email=ana@example.com#seccion',
            'source-file': 'https://gotogym.store/otro.js',
        }}
        with self.assertLogs('gotogym.csp', level='WARNING') as registro:
            respuesta = self._enviar(reporte, REMOTE_ADDR='203.0.113.77', HTTP_USER_AGENT='AgenteRaro/1.0')
        self.assertEqual(respuesta.status_code, 204)
        texto = '\n'.join(registro.output)
        self.assertIn('directiva=script-src-elem', texto)
        self.assertIn('bloqueado=https://cdn.ejemplo.test/lib.js', texto)
        self.assertIn('pagina=https://gotogym.store/tienda/', texto)
        for prohibido in ('token', 'abc123', 'ana@example.com', 'seccion', 'nonce', '203.0.113.77', 'AgenteRaro'):
            self.assertNotIn(prohibido, texto)

    def test_acepta_el_formato_de_la_api_de_reporting(self):
        reporte = [{'type': 'csp-violation', 'body': {
            'effectiveDirective': 'img-src', 'blockedURL': 'inline', 'documentURL': 'https://gotogym.store/x?y=1',
        }}]
        with self.assertLogs('gotogym.csp', level='WARNING') as registro:
            respuesta = self._enviar(reporte, tipo='application/reports+json')
        self.assertEqual(respuesta.status_code, 204)
        self.assertIn('directiva=img-src bloqueado=inline pagina=https://gotogym.store/x', registro.output[0])

    def test_recorta_y_limpia_lo_que_registra(self):
        reporte = {'csp-report': {
            'effective-directive': 'script-src\nFALSO: linea inventada',
            'blocked-uri': 'https://a.test/' + 'x' * 5000,
            'document-uri': 'https://a.test/\r\nINYECTADO',
        }}
        with self.assertLogs('gotogym.csp', level='WARNING') as registro:
            self._enviar(reporte)
        linea = registro.output[0]
        self.assertNotIn('\n', linea)
        self.assertNotIn('\r', linea)
        self.assertLess(len(linea), 600)

    def test_una_directiva_con_formato_raro_se_registra_como_desconocida(self):
        with self.assertLogs('gotogym.csp', level='WARNING') as registro:
            self._enviar({'csp-report': {'effective-directive': 'X' * 100}})
        self.assertIn('directiva=desconocida', registro.output[0])

    def test_rechaza_cuerpos_de_mas_de_8_kb(self):
        grande = json.dumps({'csp-report': {'blocked-uri': 'x' * 9000}})
        respuesta = self._enviar(grande)
        self.assertEqual(respuesta.status_code, 413)

    def test_el_cuerpo_sin_content_length_tambien_se_acota(self):
        # Sin la cabecera honesta, el limite se aplica leyendo.
        from django.test import RequestFactory

        from gotogym import csp

        peticion = RequestFactory().post(self.url, data='{' + 'x' * 9000, content_type='application/csp-report')
        peticion.META['CONTENT_LENGTH'] = ''
        self.assertEqual(csp.reporte(peticion).status_code, 413)

    def test_un_cuerpo_que_no_es_un_reporte_da_400(self):
        self.assertEqual(self._enviar('esto no es json').status_code, 400)
        self.assertEqual(self._enviar('[1, 2]').status_code, 400)

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_no_pide_token_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        respuesta = self._enviar({'csp-report': {'effective-directive': 'img-src'}}, cliente=cliente)
        self.assertEqual(respuesta.status_code, 204)

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_esta_limitada_por_cliente(self):
        from gotogym.csp import REPORTES_POR_MINUTO

        cache.clear()
        self.addCleanup(cache.clear)
        reporte = {'csp-report': {'effective-directive': 'img-src'}}
        with self.assertLogs('gotogym.csp', level='WARNING'):
            estados = [
                self._enviar(reporte, REMOTE_ADDR='198.51.100.5').status_code for _ in range(REPORTES_POR_MINUTO)
            ]
        self.assertEqual(set(estados), {204})
        self.assertEqual(self._enviar(reporte, REMOTE_ADDR='198.51.100.5').status_code, 429)
        # Otra IP no queda afectada.
        with self.assertLogs('gotogym.csp', level='WARNING'):
            self.assertEqual(self._enviar(reporte, REMOTE_ADDR='198.51.100.6').status_code, 204)


class ScriptsEnLineaTests(SimpleTestCase):
    """Ningun `<script>` ejecutable en linea puede quedar sin nonce: con la
    politica aplicada el navegador lo bloquearia. Los bloques de datos
    (`application/json`, `ld+json`) no se ejecutan y no lo necesitan."""

    ETIQUETA = re.compile(r'<script(?P<atributos>[^>]*)>', re.IGNORECASE)

    def test_todo_script_en_linea_lleva_nonce(self):
        raiz = Path(settings.BASE_DIR)
        sin_nonce = []
        revisadas = 0
        for plantilla in sorted(raiz.rglob('*.html')):
            partes = plantilla.relative_to(raiz).parts
            if 'templates' not in partes or 'staticfiles' in partes:
                continue
            revisadas += 1
            for coincidencia in self.ETIQUETA.finditer(plantilla.read_text(encoding='utf-8')):
                atributos = coincidencia.group('atributos')
                if re.search(r'\bsrc=', atributos) or 'json' in atributos:
                    continue
                if 'nonce="{{ csp_nonce }}"' not in atributos:
                    sin_nonce.append(f'{"/".join(partes)}: <script{atributos}>')
        self.assertGreater(revisadas, 50)  # el recorrido encuentra las plantillas
        self.assertEqual(sin_nonce, [])


class ModoDeConfiguracionTests(SimpleTestCase):
    """`CSP_MODO` se valida al arrancar: un valor mal escrito no tumba el sitio
    ni deja la politica apagada; vuelve a `reportar` y queda en el log."""

    def _cargar(self, modo):
        from .test_settings_seguridad import CLAVE, _cargar

        return _cargar(DJANGO_SECRET_KEY=CLAVE, CSP_MODO=modo)

    def test_los_tres_modos_validos_arrancan(self):
        for modo in ('reportar', 'aplicar', 'apagado', ' APLICAR '):
            with self.subTest(modo=modo):
                self.assertEqual(self._cargar(modo).returncode, 0)

    def test_un_valor_desconocido_arranca_en_modo_reportar_y_avisa(self):
        resultado = self._cargar('apagar')
        self.assertEqual(resultado.returncode, 0)
        self.assertIn('CSP_MODO', resultado.stderr)
