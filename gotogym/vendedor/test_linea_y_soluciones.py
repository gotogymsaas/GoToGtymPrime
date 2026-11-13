"""Linea de la prenda en la evidencia, enlaces a otras soluciones y motivo
de los errores del Coach."""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import translation

from . import coach_client, contrato, evidencia, paquete, respuesta
from .test_paquete import ANTES, _peticion
from .test_utilidades import aislar_catalogo, crear_producto

URL = '/es/vendedor/mensaje/'


def _respuesta_coach(**meta):
    return {'reply': '', 'meta': {'status': 'error', 'agents_used': [], 'evidence_refs': [], **meta}}


class CodigoDeErrorDelCoachTests(TestCase):
    def test_el_motivo_del_coach_se_conserva(self):
        validada = contrato.validar_respuesta(_respuesta_coach(error_code='validation_failed'))
        self.assertFalse(validada.ok)
        self.assertEqual(validada.meta.codigo_error, 'validation_failed')

    def test_un_motivo_con_otra_forma_se_ignora_sin_rechazar_la_respuesta(self):
        for raro in ('Texto libre con espacios', 'x' * 41, 7, None, '<script>'):
            with self.subTest(raro=raro):
                self.assertEqual(contrato.validar_respuesta(_respuesta_coach(error_code=raro)).meta.codigo_error, '')

    def test_un_rechazo_de_contenido_no_es_una_caida(self):
        self.assertTrue(coach_client.CoachNoDisponible('error_del_coach', detalle='validation_failed').es_de_contenido)
        self.assertFalse(coach_client.CoachNoDisponible('error_del_coach', detalle='unavailable').es_de_contenido)
        self.assertFalse(coach_client.CoachNoDisponible('error_del_coach').es_de_contenido)
        self.assertFalse(coach_client.CoachNoDisponible('timeout').es_de_contenido)


@override_settings(VENDEDOR_ENABLED=True)
class RegistroDelMotivoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        aislar_catalogo()
        crear_producto('Leggins Quantum', [('M', 'gris', 5)])

    def _enviar_con_fallo(self, detalle):
        cliente = mock.Mock()
        cliente.enviar.side_effect = coach_client.CoachNoDisponible('error_del_coach', detalle=detalle)
        with mock.patch.object(coach_client, 'obtener_cliente', return_value=cliente), \
                mock.patch.object(coach_client, 'registrar_fallo') as registrar, \
                self.assertLogs('vendedor.views', level='WARNING') as registro:
            respuesta_http = self.client.post(URL, data=json.dumps({'message': 'hola'}), content_type='application/json')
        return respuesta_http, registrar, registro

    def test_el_log_dice_el_motivo_y_no_abre_el_circuito(self):
        respuesta_http, registrar, registro = self._enviar_con_fallo('validation_failed')

        self.assertEqual(respuesta_http.status_code, 502)
        self.assertEqual(respuesta_http.json()['error'], 'error')
        self.assertIn('error_del_coach: validation_failed', registro.output[0])
        self.assertNotIn('hola', registro.output[0], 'el texto del visitante nunca va al log')
        registrar.assert_not_called()

    def test_una_falla_del_modelo_si_cuenta_para_el_circuito(self):
        _, registrar, _ = self._enviar_con_fallo('unavailable')
        registrar.assert_called_once()


@override_settings(VENDEDOR_SOLUCIONES={'coach_app': 'https://app.example.test/', 'developers': 'https://dev.example.test/'})
class EnlaceAOtraSolucionTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        crear_producto('Leggins Quantum', [('M', 'gris', 5)])
        with translation.override('es'):
            self.solicitud = paquete.armar_solicitud(_peticion(), 'hola', 'shop-abc', request_id='req-1', ahora=ANTES)

    def _sanear(self, acciones):
        validada = contrato.validar_respuesta({
            'reply': 'Para tus rutinas está la app de Quantum Coach.', 'ui_actions': acciones,
            'meta': {'status': 'ok', 'agents_used': [], 'evidence_refs': []},
        })
        return respuesta.sanear(validada, self.solicitud)

    def test_la_direccion_y_el_texto_los_pone_la_tienda(self):
        segura = self._sanear([{'type': 'open_solution', 'solution': 'coach_app',
                                'url': 'https://malicioso.example/', 'label': 'Haz clic'}])

        self.assertEqual(segura.acciones, [{
            'type': 'open_solution', 'solution': 'coach_app',
            'url': 'https://app.example.test/', 'label': 'Abrir Quantum Coach',
        }])

    def test_una_solucion_desconocida_se_descarta(self):
        segura = self._sanear([{'type': 'open_solution', 'solution': 'banco'}, {'type': 'open_solution'}])
        self.assertEqual(segura.acciones, [])
        self.assertEqual(segura.descartadas, 2)

    @override_settings(VENDEDOR_SOLUCIONES={'coach_app': 'http://inseguro.example/'})
    def test_sin_https_no_hay_boton(self):
        self.assertEqual(self._sanear([{'type': 'open_solution', 'solution': 'coach_app'}]).acciones, [])
        self.assertEqual(respuesta.urls_de_soluciones(), [])

    def test_el_panel_recibe_solo_las_direcciones_declaradas(self):
        self.assertEqual(respuesta.urls_de_soluciones(), ['https://app.example.test/', 'https://dev.example.test/'])


class LineaEnLaEvidenciaTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        self.dama, _ = crear_producto('Top para dama', [('M', 'gris', 3)])
        self.caballero, _ = crear_producto('Chaqueta para caballero', [('L', 'negro', 3)])
        self.sin_linea, _ = crear_producto('Botella deportiva', [('UNICA', 'azul', 3)])

    def _ids(self, mensaje='Quiero algo para entrenar', **kwargs):
        return [c['product_id'] for c in evidencia.candidatos(mensaje, **kwargs)]

    def test_cada_candidato_lleva_su_linea_y_sin_clasificar_no_la_lleva(self):
        por_id = {c['product_id']: c for c in evidencia.candidatos('entrenar')}
        self.assertEqual(por_id[self.dama.id]['line'], 'dama')
        self.assertEqual(por_id[self.caballero.id]['line'], 'caballero')
        self.assertNotIn('line', por_id[self.sin_linea.id])

    def test_la_preferencia_pone_primero_las_prendas_de_esa_linea(self):
        self.assertEqual(self._ids(linea_preferida='caballero')[0], self.caballero.id)
        self.assertEqual(self._ids(linea_preferida='dama')[0], self.dama.id)

    def test_la_preferencia_no_esconde_la_otra_linea(self):
        self.assertIn(self.dama.id, self._ids(linea_preferida='caballero'))

    def test_pedir_la_otra_linea_con_palabras_la_sube(self):
        self.assertEqual(self._ids('busco un regalo para mujer', linea_preferida='caballero')[0], self.dama.id)

    def test_hombre_encuentra_las_prendas_de_caballero(self):
        self.assertEqual(self._ids('algo para hombre')[0], self.caballero.id)


class PreferenciaEnElPaqueteTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        crear_producto('Chaqueta para caballero', [('L', 'negro', 3)])
        self.usuario = get_user_model().objects.create_user(email='p@example.com', username='p', password='x')

    def _armar(self, usuario=None):
        with translation.override('es'):
            return paquete.armar_solicitud(_peticion(usuario), 'hola', 'shop-abc', request_id='req-1', ahora=ANTES)

    def test_viaja_solo_si_la_persona_la_guardo(self):
        self.assertNotIn('line_preference', self._armar(self.usuario)['visitor'])
        self.usuario.clothing_line = 'caballero'
        self.usuario.save()
        solicitud = self._armar(self.usuario)
        self.assertEqual(solicitud['visitor']['line_preference'], 'caballero')
        contrato.validar_solicitud(solicitud)

    def test_un_visitante_anonimo_no_la_lleva(self):
        self.assertNotIn('line_preference', self._armar()['visitor'])

    def test_el_contrato_rechaza_valores_fuera_de_la_lista(self):
        solicitud = self._armar()
        solicitud['visitor']['line_preference'] = 'caballero'
        with self.assertRaises(contrato.ContratoInvalido):
            contrato.validar_solicitud(solicitud)  # anonimo
        solicitud = self._armar()
        solicitud['evidence']['candidates'][0]['line'] = 'nino'
        with self.assertRaises(contrato.ContratoInvalido):
            contrato.validar_solicitud(solicitud)
