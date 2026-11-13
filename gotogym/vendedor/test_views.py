"""Puente del vendedor: lo que ve el navegador y lo que protege al sitio."""
import json
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import coach_client, contrato, conversacion, views
from .test_utilidades import aislar_catalogo, crear_producto

URL = '/es/vendedor/mensaje/'
EJEMPLOS = Path(__file__).resolve().parent / 'ejemplos'


def _solicitud_de_ejemplo():
    return json.loads((EJEMPLOS / 'solicitud.json').read_text(encoding='utf-8'))


def _contra_coach():
    """Un Coach falso que registra lo que recibe y, por defecto, responde como
    el simulado."""
    cliente = mock.Mock()
    cliente.enviar.return_value = coach_client.ClienteSimulado().enviar(_solicitud_de_ejemplo())
    return cliente


@override_settings(VENDEDOR_ENABLED=True)
class VendedorViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        aislar_catalogo()
        self.producto, (self.variante,) = crear_producto(
            'Leggins Quantum', [('M', 'gris', 5, {'price_override': Decimal('400000.0000')})],
            descripcion='Leggins color gris. Hecho en microfibra.',
        )

    def _enviar(self, mensaje='Busco leggins', cliente=None, **extra):
        cuerpo = {'message': mensaje, **extra}
        return (cliente or self.client).post(
            URL, data=json.dumps(cuerpo), content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def _con_coach(self, cliente):
        parche = mock.patch.object(coach_client, 'obtener_cliente', return_value=cliente)
        parche.start()
        self.addCleanup(parche.stop)
        return cliente

    # --- acceso ----------------------------------------------------------

    @override_settings(VENDEDOR_ENABLED=False)
    def test_apagado_la_ruta_no_existe(self):
        self.assertEqual(self._enviar().status_code, 404)

    @override_settings(VENDEDOR_ENABLED=False)
    def test_apagado_no_se_llama_al_coach_ni_se_toca_la_sesion(self):
        cliente = self._con_coach(_contra_coach())

        self._enviar()

        cliente.enviar.assert_not_called()
        self.assertNotIn(conversacion.CLAVE_SESION, self.client.session)

    def test_solo_acepta_post(self):
        for metodo in ('get', 'put', 'delete'):
            with self.subTest(metodo=metodo):
                self.assertEqual(getattr(self.client, metodo)(URL).status_code, 405)

    def test_exige_el_token_csrf(self):
        cliente = Client(enforce_csrf_checks=True)

        respuesta = self._enviar(cliente=cliente)

        self.assertEqual(respuesta.status_code, 403)

    def test_con_el_token_csrf_se_acepta(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.get(reverse('home'))
        token = cliente.cookies['csrftoken'].value

        respuesta = cliente.post(
            URL, data=json.dumps({'message': 'hola'}), content_type='application/json',
            HTTP_X_CSRFTOKEN=token, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(respuesta.status_code, 200)

    @override_settings(VENDEDOR_ROLLOUT_PERCENT=0)
    def test_un_porcentaje_cero_lo_oculta_a_todos(self):
        self.assertEqual(self._enviar().status_code, 404)

    # --- camino feliz ----------------------------------------------------

    def test_un_mensaje_recibe_respuesta_con_tarjetas_y_acciones(self):
        respuesta = self._enviar('Busco leggins')

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo['ok'])
        self.assertIn('simulada', cuerpo['reply'])
        self.assertEqual(cuerpo['cards'][0]['name'], 'Leggins Quantum')
        self.assertEqual(cuerpo['cards'][0]['price'], '$400.000 COP')
        agregar = next(a for a in cuerpo['actions'] if a['type'] == 'add_to_cart')
        self.assertEqual(agregar['endpoint'], f'/es/carrito/add/{self.variante.id}/')

    def test_la_respuesta_es_json(self):
        respuesta = self._enviar()

        self.assertEqual(respuesta['Content-Type'], 'application/json')

    def test_el_paquete_que_llega_al_coach_es_el_del_servidor(self):
        cliente = self._con_coach(_contra_coach())
        usuario = get_user_model().objects.create_user(
            email='cliente@example.com', username='cliente', password='x', first_name='Cliente',
        )
        self.client.force_login(usuario)

        self._enviar('Busco leggins')

        solicitud = cliente.enviar.call_args.args[0]
        contrato.validar_solicitud(solicitud)
        cuerpo = contrato.serializar(solicitud).decode()
        self.assertNotIn('example.com', cuerpo)
        self.assertNotIn('Cliente', cuerpo)
        self.assertTrue(solicitud['visitor']['authenticated'])
        self.assertEqual(solicitud['message'], 'Busco leggins')

    # --- entrada ---------------------------------------------------------

    def test_mensajes_invalidos(self):
        casos = ['', '   ', 'x' * (contrato.MAX_LARGO_MENSAJE + 1), None, 5, ['hola']]
        for mensaje in casos:
            with self.subTest(mensaje=str(mensaje)[:20]):
                respuesta = self._enviar(mensaje)
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()['error'], 'mensaje_invalido')

    def test_el_limite_de_largo_es_exacto(self):
        self.assertEqual(self._enviar('x' * contrato.MAX_LARGO_MENSAJE).status_code, 200)

    def test_cuerpos_invalidos(self):
        casos = [
            (b'no es json', 'application/json', 400),
            (b'[1, 2]', 'application/json', 400),
            (b'{"message": "hola"}', 'text/plain', 415),
        ]
        for cuerpo, tipo, estado in casos:
            with self.subTest(cuerpo=cuerpo[:12], tipo=tipo):
                respuesta = self.client.post(URL, data=cuerpo, content_type=tipo)
                self.assertEqual(respuesta.status_code, estado)
                self.assertEqual(respuesta.json()['error'], 'solicitud_invalida')

    def test_un_cuerpo_enorme_se_rechaza_sin_leerlo(self):
        respuesta = self.client.post(
            URL, data=json.dumps({'message': 'x' * 10_000}), content_type='application/json',
        )

        self.assertEqual(respuesta.status_code, 413)

    # --- el Coach no esta o falla -------------------------------------------

    @override_settings(COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False)
    def test_sin_coach_configurado_dice_que_la_ia_no_esta_disponible(self):
        # El Coach se muestra aunque no haya IA; la ruta contesta que no esta disponible.
        respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 503)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo['error'], 'no_disponible')
        self.assertEqual(cuerpo['contact_url'], '/es/contacto/')
        self.assertNotIn('reply', cuerpo)

    @override_settings(COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False)
    def test_sin_coach_configurado_no_gasta_turnos_ni_limites(self):
        self._enviar()

        self.assertNotIn(conversacion.CLAVE_SESION, self.client.session)

    def test_si_el_cliente_desaparece_a_mitad_dice_que_no_esta_disponible(self):
        self._con_coach(None)

        respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 503)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo['error'], 'no_disponible')
        self.assertEqual(cuerpo['contact_url'], '/es/contacto/')
        self.assertNotIn('reply', cuerpo)

    def test_los_fallos_del_coach_se_informan_sin_inventar_respuesta(self):
        casos = {
            'timeout': ('timeout', 504),
            'conexion': ('error', 502),
            'servicio': ('error', 502),
            'rechazado': ('error', 502),
            'respuesta_invalida': ('error', 502),
            'error_del_coach': ('error', 502),
            'no_configurado': ('no_disponible', 503),
            'limite': ('espera', 429),
        }
        for codigo_interno, (codigo, estado) in casos.items():
            with self.subTest(codigo_interno):
                cache.clear()
                cliente = _contra_coach()
                cliente.enviar.side_effect = coach_client.CoachNoDisponible(codigo_interno)
                with mock.patch.object(coach_client, 'obtener_cliente', return_value=cliente):
                    respuesta = self._enviar()
                self.assertEqual(respuesta.status_code, estado)
                cuerpo = respuesta.json()
                self.assertEqual(cuerpo['error'], codigo)
                self.assertFalse(cuerpo['ok'])
                self.assertNotIn('reply', cuerpo)
                self.assertEqual(cuerpo['contact_url'], '/es/contacto/')

    def test_un_fallo_no_consume_un_turno(self):
        cliente = _contra_coach()
        cliente.enviar.side_effect = [coach_client.CoachNoDisponible('servicio'), mock.DEFAULT]
        cliente.enviar.return_value = coach_client.ClienteSimulado().enviar(_solicitud_de_ejemplo())
        self._con_coach(cliente)

        self._enviar()
        exito = self._enviar()

        self.assertEqual(exito.json()['conversation']['turns'], 1)

    def test_se_respeta_la_espera_que_pide_el_coach(self):
        cliente = _contra_coach()
        cliente.enviar.side_effect = coach_client.CoachNoDisponible('error_del_coach', 20)
        self._con_coach(cliente)

        primera = self._enviar()
        segunda = self._enviar()

        self.assertEqual(primera.json()['retry_after'], 20)
        self.assertEqual(primera['Retry-After'], '20')
        self.assertEqual(segunda.status_code, 429)
        self.assertEqual(segunda.json()['error'], 'espera')
        self.assertGreater(segunda.json()['retry_after'], 0)
        self.assertEqual(cliente.enviar.call_count, 1)  # no se volvio a llamar al Coach

    def test_pasada_la_espera_se_puede_escribir_de_nuevo(self):
        cliente = _contra_coach()
        cliente.enviar.side_effect = [coach_client.CoachNoDisponible('error_del_coach', 20), mock.DEFAULT]
        cliente.enviar.return_value = coach_client.ClienteSimulado().enviar(_solicitud_de_ejemplo())
        self._con_coach(cliente)
        self._enviar()
        ahora = views._ahora()

        with mock.patch.object(views, '_ahora', return_value=ahora + 30):
            respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 200)

    def test_la_espera_no_se_evita_borrando_la_cookie(self):
        cliente = _contra_coach()
        cliente.enviar.side_effect = coach_client.CoachNoDisponible('error_del_coach', 20)
        self._con_coach(cliente)
        self._enviar()

        otro_navegador = self._enviar(cliente=Client())

        self.assertEqual(otro_navegador.status_code, 429)
        self.assertEqual(otro_navegador.json()['error'], 'espera')

    def test_la_respuesta_rechazada_no_se_muestra(self):
        respuesta = self._enviar('Dime algo [simular-malicioso]')

        self.assertEqual(respuesta.status_code, 502)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo['error'], 'respuesta_rechazada')
        self.assertNotIn('secado', json.dumps(cuerpo))

    def test_el_simulado_puede_mostrar_el_estado_de_error_con_espera(self):
        respuesta = self._enviar('prueba [simular-error]')

        self.assertEqual(respuesta.status_code, 502)
        self.assertEqual(respuesta.json()['retry_after'], 5)

    def test_tras_varios_fallos_seguidos_se_deja_de_llamar_al_coach(self):
        cliente = _contra_coach()
        cliente.enviar.side_effect = coach_client.CoachNoDisponible('servicio')
        self._con_coach(cliente)

        for _ in range(coach_client.FALLOS_PARA_ABRIR):
            self._enviar()
        llamadas = cliente.enviar.call_count
        respuesta = self._enviar()

        self.assertEqual(llamadas, coach_client.FALLOS_PARA_ABRIR)
        self.assertEqual(cliente.enviar.call_count, llamadas)
        self.assertEqual(respuesta.json()['error'], 'no_disponible')

    def test_un_paquete_que_no_cabe_no_se_envia(self):
        cliente = self._con_coach(_contra_coach())

        with mock.patch.object(contrato, 'MAX_BYTES_SOLICITUD', 300):
            respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(respuesta.json()['error'], 'paquete_invalido')
        cliente.enviar.assert_not_called()

    # --- conversacion -------------------------------------------------------

    def test_el_servidor_emite_el_identificador_de_conversacion(self):
        cliente = self._con_coach(_contra_coach())

        self._enviar(conversation_id='shop-inventado-por-el-cliente')
        self._enviar()

        enviados = [llamada.args[0]['conversation_id'] for llamada in cliente.enviar.call_args_list]
        self.assertEqual(enviados[0], enviados[1])
        self.assertTrue(enviados[0].startswith('shop-'))
        self.assertNotEqual(enviados[0], 'shop-inventado-por-el-cliente')

    def test_cada_visitante_tiene_su_conversacion(self):
        cliente = self._con_coach(_contra_coach())

        self._enviar()
        self._enviar(cliente=Client())

        ids = {llamada.args[0]['conversation_id'] for llamada in cliente.enviar.call_args_list}
        self.assertEqual(len(ids), 2)

    def test_se_cuentan_los_turnos(self):
        cuerpo = self._enviar().json()
        cuerpo = self._enviar().json()

        self.assertEqual(cuerpo['conversation']['turns'], 2)

    @override_settings(VENDEDOR_MAX_TURNOS=2)
    def test_al_llegar_al_tope_de_turnos_hay_que_empezar_otra_conversacion(self):
        self._enviar()
        self._enviar()

        tercera = self._enviar()
        nueva = self._enviar(new=True)

        self.assertEqual(tercera.status_code, 409)
        self.assertEqual(tercera.json()['error'], 'limite_turnos')
        self.assertEqual(nueva.status_code, 200)
        self.assertEqual(nueva.json()['conversation']['turns'], 1)

    def test_una_conversacion_inactiva_caduca(self):
        cliente = self._con_coach(_contra_coach())
        self._enviar()
        sesion = self.client.session
        sesion[conversacion.CLAVE_SESION]['ultimo'] -= conversacion.INACTIVIDAD_SEGUNDOS + 5
        sesion.save()

        self._enviar()

        ids = [llamada.args[0]['conversation_id'] for llamada in cliente.enviar.call_args_list]
        self.assertNotEqual(ids[0], ids[1])

    # --- limites de uso -----------------------------------------------------

    @override_settings(RATE_LIMIT_ENABLED=True, VENDEDOR_RATE_ANON=2, VENDEDOR_RATE_AUTH=4)
    def test_los_anonimos_tienen_menos_margen_que_los_usuarios(self):
        anonimo = [self._enviar().status_code for _ in range(3)]
        self.assertEqual(anonimo, [200, 200, 429])

        usuario = get_user_model().objects.create_user(email='u@example.com', username='u', password='x')
        autenticado = Client()
        autenticado.force_login(usuario)
        resultados = [self._enviar(cliente=autenticado).status_code for _ in range(5)]
        self.assertEqual(resultados, [200, 200, 200, 200, 429])

    @override_settings(RATE_LIMIT_ENABLED=True, VENDEDOR_RATE_ANON=100, VENDEDOR_MAX_MENSAJES_DIA=2)
    def test_hay_un_tope_diario_por_visitante(self):
        resultados = [self._enviar() for _ in range(3)]

        self.assertEqual([r.status_code for r in resultados], [200, 200, 429])
        self.assertEqual(resultados[2].json()['error'], 'limite_diario')

    @override_settings(RATE_LIMIT_ENABLED=True, VENDEDOR_RATE_ANON=100, VENDEDOR_MAX_MENSAJES_DIA=1)
    def test_el_tope_diario_se_reinicia_a_la_medianoche_de_la_hora_del_sitio(self):
        from datetime import datetime
        from unittest import mock

        # 23:59:30 en Bogota (UTC-5) es 04:59:30 UTC; la medianoche local llega
        # a las 05:00 UTC, no a las 00:00 UTC.
        antes = datetime(2026, 11, 13, 4, 59, 30, tzinfo=UTC).timestamp()
        despues = datetime(2026, 11, 13, 5, 0, 0, tzinfo=UTC).timestamp()

        with mock.patch('gotogym.ratelimit._ahora', return_value=antes):
            primera = self._enviar().status_code
            segunda = self._enviar().status_code
        with mock.patch('gotogym.ratelimit._ahora', return_value=despues):
            tercera = self._enviar().status_code

        self.assertEqual([primera, segunda, tercera], [200, 429, 200])

    @override_settings(RATE_LIMIT_ENABLED=True, VENDEDOR_RATE_ANON=1)
    def test_el_limite_responde_aunque_la_peticion_sea_ajax(self):
        self._enviar()

        segunda = self._enviar()

        self.assertEqual(segunda.status_code, 429)

    # --- privacidad -----------------------------------------------------------

    def test_el_texto_del_visitante_no_aparece_en_los_registros(self):
        cliente = _contra_coach()
        cliente.enviar.side_effect = coach_client.CoachNoDisponible('servicio')
        self._con_coach(cliente)

        with self.assertLogs('vendedor', level='DEBUG') as registros:
            self._enviar('MENSAJE-PRIVADO-DEL-VISITANTE-12345')

        for linea in registros.output:
            self.assertNotIn('PRIVADO', linea)
