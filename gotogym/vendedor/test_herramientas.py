"""Herramientas del chat de Quantum Coach en la tienda: adjuntar un archivo
(lectura en memoria y extracto en el turno), dictado por voz de respaldo y el
menu "+" del panel."""
import io
import math
import struct
import wave
import zipfile
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import coach_client, contrato, documento, views, voz
from .test_utilidades import aislar_catalogo, crear_producto

URL_DOCUMENTO = '/es/vendedor/documento/'
URL_VOZ = '/es/vendedor/voz/'


# --- Archivos de prueba ----------------------------------------------------------

def pdf_con_texto(texto):
    """PDF minimo de una pagina con `texto` en Helvetica."""
    contenido = f'BT /F1 12 Tf 72 720 Td ({texto}) Tj ET'.encode('latin-1')
    objetos = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R '
        b'/Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length %d >>\nstream\n' % len(contenido) + contenido + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    salida = b'%PDF-1.4\n'
    posiciones = []
    for numero, objeto in enumerate(objetos, 1):
        posiciones.append(len(salida))
        salida += b'%d 0 obj\n' % numero + objeto + b'\nendobj\n'
    inicio_xref = len(salida)
    salida += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objetos) + 1)
    for posicion in posiciones:
        salida += b'%010d 00000 n \n' % posicion
    salida += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objetos) + 1, inicio_xref)
    return salida


def pdf_con_clave():
    from pypdf import PdfWriter

    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    escritor.encrypt(user_password='secreta', owner_password='duena')
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def xlsx(filas, titulo='Pedido'):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = titulo
    for fila in filas:
        hoja.append(fila)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def wav(segundos=1.0, frecuencia=voz.FRECUENCIA, canales=1, ancho=2):
    cuadros = int(segundos * frecuencia)
    salida = io.BytesIO()
    with wave.open(salida, 'wb') as audio:
        audio.setnchannels(canales)
        audio.setsampwidth(ancho)
        audio.setframerate(frecuencia)
        muestra = struct.Struct('<h')
        datos = b''.join(muestra.pack(int(8000 * math.sin(i / 8))) * canales for i in range(cuadros))
        if ancho == 1:
            datos = bytes(cuadros * canales)
        audio.writeframes(datos)
    return salida.getvalue()


# --- Lectura de documentos ----------------------------------------------------------

class LeerDocumentoTests(SimpleTestCase):
    def test_texto_plano(self):
        leido = documento.leer(b'Necesito 20 camisetas negras talla M.', 'pedido.txt')
        self.assertEqual((leido.formato, leido.recortado), ('txt', False))
        self.assertIn('20 camisetas negras talla M', leido.extracto)

    def test_oculta_correos_telefonos_documentos_y_enlaces(self):
        texto = ('Escríbeme a ana.perez@example.com o al +57 300 123 4567. Cédula 1.020.345.678. '
                 'Mira https://ejemplo.com/pedido?token=abc. Quiero 3 leggins talla S.')
        extracto = documento.leer(texto.encode()).extracto
        for dato in ('@', '300', '4567', '1.020', 'https', 'token'):
            self.assertNotIn(dato, extracto)
        self.assertIn('3 leggins talla S', extracto)
        self.assertIn(documento.OCULTO, extracto)

    def test_csv_con_punto_y_coma(self):
        datos = b'Prenda;Talla;Cantidad\nCamiseta;M;20\nLeggins;S;3\n'
        leido = documento.leer(datos, 'pedido.csv')
        self.assertEqual(leido.formato, 'csv')
        self.assertIn('Camiseta | M | 20', leido.extracto)

    def test_excel(self):
        leido = documento.leer(xlsx([['Prenda', 'Talla', 'Cantidad'], ['Leggins', 'S', 3], [None, None, None]]))
        self.assertEqual(leido.formato, 'xlsx')
        self.assertIn('[Pedido]', leido.extracto)
        self.assertIn('Leggins | S | 3', leido.extracto)

    def test_pdf_con_texto(self):
        leido = documento.leer(pdf_con_texto('Busco una chaqueta negra para correr'))
        self.assertEqual(leido.formato, 'pdf')
        self.assertIn('chaqueta negra', leido.extracto)

    def test_pdf_con_clave(self):
        with self.assertRaises(documento.DocumentoInvalido) as error:
            documento.leer(pdf_con_clave())
        self.assertEqual(error.exception.codigo, 'protegido')

    def test_pdf_roto(self):
        with self.assertRaises(documento.DocumentoInvalido) as error:
            documento.leer(b'%PDF-1.4\nesto no es un pdf de verdad')
        self.assertEqual(error.exception.codigo, 'ilegible')

    def test_binario_o_zip_que_no_es_excel(self):
        zipeado = io.BytesIO()
        with zipfile.ZipFile(zipeado, 'w') as archivo:
            archivo.writestr('hola.txt', 'hola')
        for datos in (bytes(range(256)) * 4, zipeado.getvalue()):
            with self.subTest(datos=datos[:4]):
                with self.assertRaises(documento.DocumentoInvalido) as error:
                    documento.leer(datos)
                self.assertEqual(error.exception.codigo, 'formato')

    def test_excel_que_descomprimido_es_enorme(self):
        with mock.patch.object(documento, 'MAX_BYTES_DESCOMPRIMIDOS', 100):
            with self.assertRaises(documento.DocumentoInvalido) as error:
                documento.leer(xlsx([['a' * 500]]))
        self.assertEqual(error.exception.codigo, 'grande')

    def test_vacio_grande_y_sin_texto(self):
        casos = (
            (b'', 'vacio'),
            (b'a' * (documento.MAX_BYTES_SUBIDA + 1), 'grande'),
            (b'300 123 4567\n\n   ', 'sin_texto'),
        )
        for datos, codigo in casos:
            with self.subTest(codigo):
                with self.assertRaises(documento.DocumentoInvalido) as error:
                    documento.leer(datos)
                self.assertEqual(error.exception.codigo, codigo)

    def test_un_texto_largo_se_recorta_en_una_palabra(self):
        leido = documento.leer(('camiseta negra ' * 400).encode())
        self.assertTrue(leido.recortado)
        self.assertLessEqual(len(leido.extracto), contrato.MAX_LARGO_EXTRACTO)
        self.assertTrue(leido.extracto.endswith(('camiseta', 'negra')))


# --- Voz ---------------------------------------------------------------------------

class VozTests(SimpleTestCase):
    def test_prepara_un_wav_valido(self):
        self.assertEqual(voz.preparar(wav(1.0)).milisegundos, 1000)

    def test_rechaza_lo_que_no_es_wav_de_16_khz_mono(self):
        casos = (
            (b'no soy audio', 'formato'),
            (wav(frecuencia=44100), 'formato'),
            (wav(canales=2), 'formato'),
            (wav(ancho=1), 'formato'),
            (wav(0.1), 'corta'),
            (wav(31), 'larga'),
            (b'', 'vacia'),
        )
        for datos, codigo in casos:
            with self.subTest(codigo):
                with self.assertRaises(voz.VozInvalida) as error:
                    voz.preparar(datos)
                self.assertEqual(error.exception.codigo, codigo)

    def test_idioma_hablado(self):
        self.assertEqual(voz.idioma_hablado('es', 'es-MX'), 'es-MX')
        self.assertEqual(voz.idioma_hablado('es', 'en-US'), 'es-CO')
        self.assertEqual(voz.idioma_hablado('es', '<script>'), 'es-CO')
        self.assertEqual(voz.idioma_hablado('en', ''), 'en-US')

    def test_solicitud_y_respuesta(self):
        solicitud = voz.armar_solicitud(voz.preparar(wav(1.0)), 'es', 'es-AR', request_id='req-voz-0001', ahora=10)
        self.assertEqual(solicitud['language'], 'es-AR')
        self.assertEqual(solicitud['audio']['duration_ms'], 1000)
        self.assertEqual(voz.validar_respuesta({'meta': {'status': 'ok'}, 'text': '  hola   coach '}).texto, 'hola coach')
        error = voz.validar_respuesta({'meta': {'status': 'error', 'error_code': 'stt_failed', 'retry_after_seconds': 5}})
        self.assertEqual((error.ok, error.codigo_error, error.reintentar_en), (False, 'stt_failed', 5))
        for malo in ({}, {'meta': {'status': 'ok'}, 'text': 3}, {'meta': {'status': 'raro'}}):
            with self.subTest(malo):
                with self.assertRaises(contrato.ContratoInvalido):
                    voz.validar_respuesta(malo)

    def test_url_de_voz_sale_de_la_del_turno(self):
        self.assertEqual(coach_client.url_de_voz('https://coach.example/api/commerce/agent/message/'),
                         'https://coach.example/api/commerce/speech/transcribe/')
        self.assertEqual(coach_client.url_de_voz('https://coach.example/otra/'), '')

    def test_cliente_http_transcribe_y_entiende_un_coach_sin_voz(self):
        cliente = coach_client.ClienteHttp('https://coach.example/api/commerce/agent/message/', 'shop', 'x' * 32, 5,
                                           url_voz='https://coach.example/api/commerce/speech/transcribe/')
        solicitud = voz.armar_solicitud(voz.preparar(wav(1.0)), 'es')
        ok = mock.Mock(status_code=200, headers={})
        ok.json.return_value = {'meta': {'status': 'ok'}, 'text': 'busco leggins'}
        no_existe = mock.Mock(status_code=404, headers={})
        no_existe.json.return_value = {}
        with mock.patch.object(coach_client.requests, 'post', return_value=ok) as post:
            self.assertEqual(cliente.transcribir(solicitud).texto, 'busco leggins')
        self.assertEqual(post.call_args.kwargs['headers']['X-Vendedor-Contract'], voz.VERSION_CONTRATO_VOZ)
        with mock.patch.object(coach_client.requests, 'post', return_value=no_existe):
            with self.assertRaises(coach_client.CoachNoDisponible) as error:
                cliente.transcribir(solicitud)
        self.assertEqual(error.exception.codigo, 'no_soportado')


# --- Contrato ------------------------------------------------------------------------

def _solicitud_con(adjunto):
    return {
        'request_id': 'req-0001', 'conversation_id': 'shop-12345678', 'locale': 'es', 'message': 'hola',
        'timestamp': 1, 'visitor': {'subject': 'shop_v_abc12345', 'authenticated': False},
        'page': {'url_name': '', 'product_id': None, 'variant_id': None, 'filtro': ''},
        'cart': {'count': 0, 'subtotal': '0.00', 'lines': []},
        'shop_flags': {'purchases_paused': False, 'payments_live': False, 'currency': 'COP'},
        'evidence': {'candidates': [], 'policies': [], 'promotions': [],
                     'claims_policy': {'version': 'v1', 'prohibited': []}},
        'attachment': adjunto,
    }


class ContratoAdjuntoTests(SimpleTestCase):
    def test_forma_cerrada(self):
        base = {'source': 'customer_document', 'format': 'pdf', 'excerpt': 'lista de prendas', 'truncated': False}
        contrato.validar_solicitud(_solicitud_con(base))
        malos = (
            {**base, 'source': 'otro'}, {**base, 'format': 'docx'}, {**base, 'truncated': 'no'},
            {**base, 'excerpt': ''}, {**base, 'excerpt': 'x' * (contrato.MAX_LARGO_EXTRACTO + 1)},
            {**base, 'filename': 'pedido.pdf'},
        )
        for malo in malos:
            with self.subTest(malo):
                with self.assertRaises(contrato.ContratoInvalido):
                    contrato.validar_solicitud(_solicitud_con(malo))


# --- Rutas -------------------------------------------------------------------------------

def _archivo(datos, nombre='pedido.txt', tipo='text/plain'):
    return SimpleUploadedFile(nombre, datos, content_type=tipo)


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100)
class DocumentoVistaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        aislar_catalogo()
        self.leggins, _ = crear_producto('Leggins negros para dama', [('S', 'negro', 3)])
        self.chaqueta, _ = crear_producto('Chaqueta impermeable', [('M', 'azul', 2)])

    def _con_coach(self):
        coach = mock.Mock()
        coach.enviar.side_effect = coach_client.ClienteSimulado().enviar
        parche = mock.patch.object(coach_client, 'obtener_cliente', return_value=coach)
        parche.start()
        self.addCleanup(parche.stop)
        return coach

    def _enviar(self, cliente=None, **datos):
        datos.setdefault('documento', _archivo(b'Quiero 3 leggins negros talla S.', 'Pedido Ana López.txt'))
        return (cliente or self.client).post(URL_DOCUMENTO, data=datos, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_el_extracto_viaja_en_el_turno_sin_el_nombre_del_archivo(self):
        coach = self._con_coach()
        respuesta = self._enviar(message='¿Tienen esto?')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['document'], {'format': 'txt', 'truncated': False})
        solicitud = coach.enviar.call_args.args[0]
        self.assertEqual(solicitud['message'], '¿Tienen esto?')
        self.assertEqual(solicitud['attachment']['source'], 'customer_document')
        self.assertIn('3 leggins negros talla S', solicitud['attachment']['excerpt'])
        self.assertNotIn('Ana', contrato.serializar(solicitud).decode())
        # El texto del archivo tambien elige candidatos.
        self.assertEqual(solicitud['evidence']['candidates'][0]['product_id'], self.leggins.id)

    def test_sin_mensaje_pone_uno_propio(self):
        coach = self._con_coach()
        self.assertEqual(self._enviar().status_code, 200)
        self.assertIn('archivo', coach.enviar.call_args.args[0]['message'])

    def test_abierto_a_visitantes_sin_cuenta(self):
        self._con_coach()
        self.assertEqual(self._enviar(cliente=Client()).status_code, 200)

    def test_archivo_que_no_se_puede_leer(self):
        coach = self._con_coach()
        casos = (
            (_archivo(bytes(range(256)) * 4, 'x.bin', 'application/octet-stream'), 400, 'documento_invalido'),
            (_archivo(b'300 123 4567'), 422, 'documento_sin_texto'),
            (_archivo(pdf_con_clave(), 'x.pdf', 'application/pdf'), 422, 'documento_protegido'),
        )
        for subida, estado, codigo in casos:
            with self.subTest(codigo):
                respuesta = self._enviar(documento=subida)
                self.assertEqual((respuesta.status_code, respuesta.json()['error']), (estado, codigo))
        coach.enviar.assert_not_called()

    def test_sin_archivo_peticion_grande_y_solo_post(self):
        self._con_coach()
        self.assertEqual(self.client.post(URL_DOCUMENTO, data={'message': 'hola'}).json()['error'], 'documento_invalido')
        respuesta = self.client.post(URL_DOCUMENTO, data={'documento': _archivo(b'hola')},
                                     CONTENT_LENGTH=str(views.MAX_BYTES_PETICION_DOCUMENTO + 1))
        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (413, 'documento_grande'))
        self.assertEqual(self.client.get(URL_DOCUMENTO).status_code, 405)

    def test_exige_el_token_csrf(self):
        self._con_coach()
        cliente = Client(enforce_csrf_checks=True)
        self.assertEqual(self._enviar(cliente=cliente).status_code, 403)

    @override_settings(VENDEDOR_ENABLED=False)
    def test_sin_vendedor_la_ruta_no_existe(self):
        self.assertEqual(self._enviar().status_code, 404)


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100)
class VozVistaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _con_coach(self, transcripcion=None, error=None):
        coach = mock.Mock()
        if error:
            coach.transcribir.side_effect = error
        else:
            coach.transcribir.return_value = transcripcion or voz.Transcripcion(texto='busco leggins talla S')
        parche = mock.patch.object(coach_client, 'obtener_cliente', return_value=coach)
        parche.start()
        self.addCleanup(parche.stop)
        return coach

    def _enviar(self, cliente=None, **datos):
        datos.setdefault('audio', _archivo(wav(1.0), 'voz.wav', 'audio/wav'))
        return (cliente or self.client).post(URL_VOZ, data=datos, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_devuelve_el_texto_dictado(self):
        coach = self._con_coach()
        respuesta = self._enviar(region='es-MX')
        self.assertEqual(respuesta.json(), {'ok': True, 'text': 'busco leggins talla S'})
        self.assertEqual(coach.transcribir.call_args.args[0]['language'], 'es-MX')

    def test_audio_invalido_no_llega_al_coach(self):
        coach = self._con_coach()
        respuesta = self._enviar(audio=_archivo(b'no soy audio', 'voz.wav', 'audio/wav'))
        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (400, 'voz_invalida'))
        respuesta = self._enviar(audio=_archivo(wav(31), 'voz.wav', 'audio/wav'))
        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (413, 'voz_larga'))
        coach.transcribir.assert_not_called()

    def test_coach_sin_voz(self):
        self._con_coach(error=coach_client.CoachNoDisponible('no_soportado', detalle='http_404'))
        respuesta = self._enviar()
        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (503, 'voz_no_disponible'))

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_tope_diario_por_persona(self):
        self._con_coach()
        with mock.patch.object(views, 'VOZ_MAX_DIA', 1):
            self.assertEqual(self._enviar().status_code, 200)
            respuesta = self._enviar()
        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (429, 'limite_voz'))

    def test_coach_simulado(self):
        with mock.patch.object(coach_client, 'obtener_cliente', return_value=coach_client.ClienteSimulado()):
            texto = self._enviar().json()['text']
        self.assertIn('simulada', texto)

    def test_exige_csrf_y_solo_post(self):
        self._con_coach()
        self.assertEqual(self._enviar(cliente=Client(enforce_csrf_checks=True)).status_code, 403)
        self.assertEqual(self.client.get(URL_VOZ).status_code, 405)


# --- Panel ---------------------------------------------------------------------------------

@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100, VENDEDOR_COACH_SIMULADO=True, COACH_API_URL='')
class PanelHerramientasTests(TestCase):
    @override_settings(VENDEDOR_IMAGEN_ACCESO='todos')
    def test_menu_con_las_cuatro_herramientas_y_el_microfono(self):
        html = Client().get(reverse('home')).content.decode()
        for marca in ('data-vendedor-mas', 'data-herramienta="camara"', 'data-herramienta="archivo"',
                      'data-herramienta="imagen"', 'data-herramienta="voz"', 'data-vendedor-microfono',
                      'data-vendedor-voz-panel', 'capture="environment"'):
            self.assertIn(marca, html)
        self.assertIn('"documentoUrl": "/es/vendedor/documento/"', html)
        self.assertIn('"vozUrl": "/es/vendedor/voz/"', html)
        self.assertIn('"imagenUrl": "/es/vendedor/imagen/"', html)

    @override_settings(VENDEDOR_IMAGEN_ACCESO='apagado')
    def test_sin_acceso_a_fotos_queda_el_archivo_sin_imagenes(self):
        html = Client().get(reverse('home')).content.decode()
        self.assertNotIn('data-herramienta="camara"', html)
        self.assertNotIn('data-herramienta="imagen"', html)
        self.assertIn('data-herramienta="archivo"', html)
        self.assertNotIn('.txt,image/', html)

    @override_settings(VENDEDOR_COACH_SIMULADO=False)
    def test_sin_ia_no_hay_herramientas(self):
        html = Client().get(reverse('home')).content.decode()
        self.assertNotIn('data-vendedor-mas', html)
        self.assertNotIn('data-vendedor-microfono', html)
