"""Busqueda por foto de punta a punta en la tienda: acceso, limites, vision,
coincidencias con el catalogo y el turno que llega al Coach."""
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import coach_client, contrato, evidencia, paquete, views, vision
from .test_imagen import foto
from .test_utilidades import aislar_catalogo, crear_producto

URL = '/es/vendedor/imagen/'
EJEMPLOS = Path(__file__).resolve().parent / 'ejemplos'


def _subida(datos=None, nombre='foto.jpg'):
    return SimpleUploadedFile(nombre, datos if datos is not None else foto(), content_type='image/jpeg')


def _descripcion(**atributos):
    return vision.Descripcion(ok=True, prenda=True, atributos=atributos, confianza=0.9)


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_IMAGEN_ACCESO='staff')
class BusquedaPorFotoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        aislar_catalogo()
        self.chaqueta, _ = crear_producto(
            'Chaqueta negra con capucha para caballero', [('M', 'negro', 4, {'price_override': Decimal('300000')})])
        self.buzo, _ = crear_producto('Buzo gris para caballero', [('L', 'gris', 2)])
        self.leggins, _ = crear_producto('Leggins negros para dama', [('S', 'negro', 3)])
        self.staff = get_user_model().objects.create_user('equipo@example.com', 'x', 'equipo', is_staff=True)
        self.cliente_normal = get_user_model().objects.create_user('cliente@example.com', 'x', 'cliente')
        self.client.force_login(self.staff)

    def _con_coach(self, descripcion=None, describir_error=None):
        """Coach falso: describe la foto como se le pida y contesta el turno
        como el simulado, guardando el paquete que recibio."""
        coach = mock.Mock()
        if describir_error:
            coach.describir.side_effect = describir_error
        else:
            coach.describir.return_value = descripcion or _descripcion(garment_type='chaqueta', colors=['negro'])
        simulado = coach_client.ClienteSimulado()
        coach.enviar.side_effect = simulado.enviar
        parche = mock.patch.object(coach_client, 'obtener_cliente', return_value=coach)
        parche.start()
        self.addCleanup(parche.stop)
        return coach

    def _enviar(self, cliente=None, **datos):
        datos.setdefault('imagen', _subida())
        return (cliente or self.client).post(URL, data=datos, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    # --- acceso -------------------------------------------------------------

    def test_por_defecto_solo_el_equipo(self):
        self._con_coach()
        anonimo = Client()
        self.assertEqual(self._enviar(cliente=anonimo).status_code, 404)
        cliente = Client()
        cliente.force_login(self.cliente_normal)
        self.assertEqual(self._enviar(cliente=cliente).status_code, 404)
        self.assertEqual(self._enviar().status_code, 200)

    @override_settings(VENDEDOR_IMAGEN_ACCESO='autenticados')
    def test_abierto_a_clientes_con_sesion(self):
        self._con_coach()
        cliente = Client()
        cliente.force_login(self.cliente_normal)
        self.assertEqual(self._enviar(cliente=cliente).status_code, 200)
        self.assertEqual(self._enviar(cliente=Client()).status_code, 404)

    @override_settings(VENDEDOR_IMAGEN_ACCESO='apagado')
    def test_apagado_la_ruta_no_existe(self):
        coach = self._con_coach()
        self.assertEqual(self._enviar().status_code, 404)
        coach.describir.assert_not_called()

    @override_settings(VENDEDOR_ENABLED=False)
    def test_sin_vendedor_la_ruta_no_existe(self):
        self.assertEqual(self._enviar().status_code, 404)

    def test_exige_el_token_csrf(self):
        self._con_coach()
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.staff)
        self.assertEqual(self._enviar(cliente=cliente).status_code, 403)

        cliente.get(reverse('home'))
        respuesta = cliente.post(URL, data={'imagen': _subida()}, HTTP_X_CSRFTOKEN=cliente.cookies['csrftoken'].value)
        self.assertEqual(respuesta.status_code, 200)

    def test_solo_post(self):
        self.assertEqual(self.client.get(URL).status_code, 405)

    # --- validacion de la subida -------------------------------------------

    def test_sin_foto_o_con_un_archivo_que_no_es_imagen(self):
        coach = self._con_coach()
        self.assertEqual(self.client.post(URL, data={'message': 'hola'}).json()['error'], 'imagen_invalida')
        respuesta = self._enviar(imagen=_subida(b'no soy una foto'))
        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (400, 'imagen_invalida'))
        coach.describir.assert_not_called()

    def test_json_en_lugar_de_formulario(self):
        respuesta = self.client.post(URL, data=json.dumps({'imagen': 'x'}), content_type='application/json')
        self.assertEqual(respuesta.status_code, 415)

    def test_peticion_demasiado_grande_se_rechaza_sin_leerla(self):
        respuesta = self.client.post(
            URL, data={'imagen': _subida()}, CONTENT_LENGTH=str(views.MAX_BYTES_PETICION_IMAGEN + 1))
        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (413, 'imagen_grande'))

    def test_texto_demasiado_largo(self):
        self._con_coach()
        respuesta = self._enviar(message='x' * (contrato.MAX_LARGO_MENSAJE + 1))
        self.assertEqual(respuesta.json()['error'], 'mensaje_invalido')

    def test_la_subida_se_queda_en_memoria(self):
        manejador = views._SubidaEnMemoria(mock.Mock(), views.MAX_BYTES_PETICION_IMAGEN)
        manejador.handle_raw_input(None, {}, views.MAX_BYTES_PETICION_IMAGEN, b'x')
        self.assertTrue(manejador.activated)
        manejador.handle_raw_input(None, {}, views.MAX_BYTES_PETICION_IMAGEN + 1, b'x')
        self.assertFalse(manejador.activated)

    # --- flujo completo -------------------------------------------------------

    def test_turno_con_las_prendas_parecidas_primero(self):
        coach = self._con_coach(_descripcion(garment_type='chaqueta', colors=['negro'], neckline='capucha'))

        respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo['ok'])
        self.assertEqual(cuerpo['visual']['summary'], ['Chaqueta', 'Con capucha', 'negro'])
        # El buzo gris es afin pero no comparte color: no cuenta como parecido.
        self.assertEqual(cuerpo['visual']['matches'], 1)
        # La foto que viaja al Coach es la copia preparada, en el contrato de vision.
        solicitud_vision = coach.describir.call_args.args[0]
        self.assertEqual(solicitud_vision['purpose'], 'similar_products')
        # El turno lleva visual_query y la chaqueta va primero entre los candidatos.
        turno = coach.enviar.call_args.args[0]
        self.assertEqual(turno['message'], 'Busco prendas parecidas a la de mi foto.')
        self.assertEqual(turno['visual_query']['matches'][0]['product_id'], self.chaqueta.id)
        self.assertEqual(turno['evidence']['candidates'][0]['product_id'], self.chaqueta.id)
        self.assertNotIn(self.leggins.id, [f['product_id'] for f in turno['visual_query']['matches']])
        self.assertNotIn('data', json.dumps(turno['visual_query']))

    def test_el_texto_del_cliente_acompana_la_foto(self):
        coach = self._con_coach()
        self._enviar(message='¿Tienen algo así en talla M?')
        self.assertEqual(coach.enviar.call_args.args[0]['message'], '¿Tienen algo así en talla M?')

    def test_en_ingles_el_mensaje_por_defecto_va_en_ingles(self):
        coach = self._con_coach()
        self.client.post('/en/vendedor/imagen/', data={'imagen': _subida()})
        turno = coach.enviar.call_args.args[0]
        self.assertEqual(turno['locale'], 'en')
        self.assertEqual(turno['message'], "I'm looking for items similar to the one in my photo.")

    def test_sin_prenda_no_gasta_un_turno(self):
        coach = self._con_coach(vision.Descripcion(ok=True, prenda=False))

        cuerpo = self._enviar().json()

        self.assertEqual((cuerpo['ok'], cuerpo['notice']), (True, 'sin_prenda'))
        coach.enviar.assert_not_called()

    def test_nada_parecido_igual_va_al_coach_con_matches_vacio(self):
        coach = self._con_coach(_descripcion(garment_type='vestido', colors=['rosa']))

        cuerpo = self._enviar().json()

        self.assertEqual(cuerpo['visual']['matches'], 0)
        self.assertEqual(coach.enviar.call_args.args[0]['visual_query']['matches'], [])

    def test_coach_sin_vision(self):
        coach = self._con_coach(describir_error=coach_client.CoachNoDisponible('no_soportado', detalle='http_404'))

        respuesta = self._enviar()

        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (503, 'imagen_no_disponible'))
        coach.enviar.assert_not_called()
        # Un fallo de vision no corta el chat de texto.
        self.assertFalse(coach_client.circuito_abierto())

    def test_foto_rechazada_por_el_coach(self):
        self._con_coach(describir_error=coach_client.CoachNoDisponible('error_del_coach', detalle='image_rejected'))
        respuesta = self._enviar()
        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (422, 'imagen_rechazada'))
        self.assertIn('vision:error_del_coach:image_rejected', respuesta.json()['diagnostic'])

    def test_con_el_coach_simulado(self):
        respuesta = self._enviar(imagen=_subida(foto(color=(15, 15, 15))))

        cuerpo = respuesta.json()
        self.assertTrue(cuerpo['ok'], cuerpo)
        self.assertIn('negro', cuerpo['visual']['summary'])

    @override_settings(RATE_LIMIT_ENABLED=True, VENDEDOR_IMAGEN_MAX_DIA=2, VENDEDOR_IMAGEN_RATE=50)
    def test_tope_diario_de_fotos(self):
        coach = self._con_coach()
        self.assertEqual(self._enviar().status_code, 200)
        self.assertEqual(self._enviar().status_code, 200)

        respuesta = self._enviar()

        self.assertEqual((respuesta.status_code, respuesta.json()['error']), (429, 'limite_imagenes'))
        self.assertEqual(coach.describir.call_count, 2)

    @override_settings(RATE_LIMIT_ENABLED=True, VENDEDOR_IMAGEN_MAX_DIA_GLOBAL=1, VENDEDOR_IMAGEN_RATE=50)
    def test_tope_global_de_la_tienda(self):
        self._con_coach()
        self.assertEqual(self._enviar().status_code, 200)
        otro = Client()
        otro.force_login(get_user_model().objects.create_user('otro@example.com', 'x', 'otro', is_staff=True))
        self.assertEqual(self._enviar(cliente=otro).json()['error'], 'limite_imagenes')


class CoincidenciasTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        self.chaqueta_negra, _ = crear_producto('Chaqueta negra para caballero', [('M', 'negro', 1)])
        self.chaqueta_gris, _ = crear_producto('Chaqueta gris para caballero', [('M', 'gris', 1)])
        self.buzo_negro, _ = crear_producto('Buzo negro para dama', [('M', 'negro', 1)])
        self.leggins_negros, _ = crear_producto('Leggins negros', [('M', 'negro', 1)])
        self.agotada, _ = crear_producto('Chaqueta negra agotada', [('M', 'negro', 0)])

    def test_orden_por_parecido_y_sin_tipos_ajenos(self):
        filas = evidencia.coincidencias_visuales({'garment_type': 'chaqueta', 'colors': ['negro']})
        ids = [f['product_id'] for f in filas]

        self.assertEqual(ids[0], self.chaqueta_negra.id)
        self.assertIn(self.chaqueta_gris.id, ids)
        self.assertIn(self.buzo_negro.id, ids)            # afin y del mismo color
        self.assertNotIn(self.leggins_negros.id, ids)     # otro tipo de prenda
        self.assertNotIn(self.agotada.id, ids)            # sin existencias
        self.assertEqual(filas[0]['matched'], ['garment_type', 'colors'])

    def test_la_linea_preferida_desempata(self):
        filas = evidencia.coincidencias_visuales({'garment_type': 'buzo'}, linea_preferida='dama')
        self.assertEqual(filas[0]['product_id'], self.buzo_negro.id)

    def test_sin_atributos_no_hay_coincidencias(self):
        self.assertEqual(evidencia.coincidencias_visuales({}), [])


class ContratoConsultaVisualTests(TestCase):
    def _solicitud(self):
        return json.loads((EJEMPLOS / 'solicitud_con_foto.json').read_text(encoding='utf-8'))

    def test_el_ejemplo_es_valido(self):
        contrato.validar_solicitud(self._solicitud())

    def test_una_coincidencia_que_no_es_candidato_se_rechaza(self):
        solicitud = self._solicitud()
        solicitud['visual_query']['matches'][0]['product_id'] = 999
        with self.assertRaisesMessage(contrato.ContratoInvalido, 'visual_query.matches[0].product_id'):
            contrato.validar_solicitud(solicitud)

    def test_atributos_fuera_del_vocabulario_o_claves_de_mas(self):
        solicitud = self._solicitud()
        solicitud['visual_query']['attributes']['garment_type'] = 'kimono'
        with self.assertRaises(contrato.ContratoInvalido):
            contrato.validar_solicitud(solicitud)
        solicitud = self._solicitud()
        solicitud['visual_query']['image'] = 'base64...'
        with self.assertRaises(contrato.ContratoInvalido):
            contrato.validar_solicitud(solicitud)

    def test_bloque_visual_del_paquete(self):
        bloque = paquete.bloque_visual(_descripcion(garment_type='top'), [])
        self.assertEqual(set(bloque), contrato.CLAVES_CONSULTA_VISUAL)


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100, VENDEDOR_IMAGEN_ACCESO='staff')
class PanelTests(TestCase):
    def test_el_boton_de_foto_solo_para_quien_tiene_acceso(self):
        self.assertNotIn('data-herramienta="camara"', self.client.get('/es/').content.decode())

        staff = get_user_model().objects.create_user('panel@example.com', 'x', 'panel', is_staff=True)
        self.client.force_login(staff)
        html = self.client.get('/es/').content.decode()

        self.assertIn('data-herramienta="camara"', html)
        self.assertIn('"imagenUrl": "/es/vendedor/imagen/"', html)
        self.assertIn('no la guardo', html)

    @override_settings(COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False)
    def test_sin_ia_no_hay_boton_de_foto(self):
        staff = get_user_model().objects.create_user('panel2@example.com', 'x', 'panel2', is_staff=True)
        self.client.force_login(staff)
        self.assertNotIn('data-herramienta="camara"', self.client.get('/es/').content.decode())
