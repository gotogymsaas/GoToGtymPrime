"""Contrato del endpoint de eventos.

Lo llama el navegador de cualquiera, asi que las pruebas se concentran en
lo que tiene que rechazar: nombres fuera de la taxonomia, lotes enormes,
propiedades arbitrarias y, sobre todo, cualquier rastro de quien es la
persona detras de la sesion.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import EventoAnalitica


class RegistrarEventosTests(TestCase):
    def setUp(self):
        self.url = reverse('analitica:registrar_eventos')

    def _enviar(self, eventos):
        return self.client.post(self.url, {'eventos': json.dumps(eventos)})

    def test_guarda_los_eventos_de_la_taxonomia(self):
        respuesta = self._enviar([
            {'nombre': 'page_view', 'ruta': '/es/welcome/', 'propiedades': {'ancho': 1440}},
            {'nombre': 'product_click', 'ruta': '/es/tienda/',
             'propiedades': {'producto': '3', 'lista': 'plp', 'posicion': '2'}},
        ])

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {'ok': True, 'guardados': 2})
        self.assertEqual(EventoAnalitica.objects.count(), 2)

        clic = EventoAnalitica.objects.get(nombre='product_click')
        self.assertEqual(clic.ruta, '/es/tienda/')
        self.assertEqual(clic.propiedades['lista'], 'plp')

    def test_descarta_nombres_fuera_de_la_taxonomia(self):
        respuesta = self._enviar([
            {'nombre': 'page_view'},
            {'nombre': 'evento_inventado'},
            {'nombre': 'DROP TABLE'},
        ])

        self.assertEqual(respuesta.json()['guardados'], 1)
        self.assertEqual(
            list(EventoAnalitica.objects.values_list('nombre', flat=True)),
            ['page_view'],
        )

    def test_no_guarda_quien_es_la_persona(self):
        usuario = get_user_model().objects.create_user(
            email='medible@example.com', username='medible', password='secret123',
            first_name='Med',
        )
        self.client.force_login(usuario)

        self._enviar([{'nombre': 'page_view'}])

        evento = EventoAnalitica.objects.get()
        self.assertTrue(evento.autenticado)
        # Ni correo, ni nombre, ni id de usuario en ningun campo.
        volcado = json.dumps({
            'ruta': evento.ruta,
            'sesion': evento.sesion,
            'propiedades': evento.propiedades,
        })
        self.assertNotIn('medible@example.com', volcado)
        self.assertNotIn('Med', volcado)
        # No se compara el pk contra el hash como substring: un hash hex es
        # una cadena de digitos y letras a-f, asi que decimales cortos como
        # el pk de un usuario de prueba pueden coincidir por pura casualidad
        # (paso justamente por esto en CI). Lo que importa es que la sesion
        # sea un hash, no la clave ni el pk en claro.
        self.assertNotEqual(evento.sesion, str(usuario.pk))
        self.assertRegex(evento.sesion, r'^[0-9a-f]{32}$')

    def test_la_sesion_se_guarda_hasheada_y_no_en_claro(self):
        self.client.get(reverse('home'))  # crea sesion
        self._enviar([{'nombre': 'page_view'}])

        evento = EventoAnalitica.objects.get()
        clave = self.client.session.session_key
        if clave:
            self.assertNotEqual(evento.sesion, clave)
            self.assertNotIn(clave, evento.sesion)

    def test_recorta_el_lote_a_un_tamano_razonable(self):
        respuesta = self._enviar([{'nombre': 'page_view'}] * 100)

        self.assertEqual(respuesta.json()['guardados'], 40)

    def test_limpia_propiedades_abusivas(self):
        self._enviar([{
            'nombre': 'search_submit',
            'propiedades': {
                'termino': 'x' * 400,
                'anidado': {'no': 'deberia entrar'},
                'lista': [1, 2, 3],
                'ok': 7,
            },
        }])

        propiedades = EventoAnalitica.objects.get().propiedades
        self.assertEqual(len(propiedades['termino']), 120)
        self.assertNotIn('anidado', propiedades)
        self.assertNotIn('lista', propiedades)
        self.assertEqual(propiedades['ok'], 7)

    def test_un_cuerpo_invalido_no_rompe_la_vista(self):
        respuesta = self.client.post(self.url, {'eventos': 'esto no es json'})

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(EventoAnalitica.objects.exists())

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class VisitanteEstableTests(TestCase):
    """El embudo no puede partirse cuando alguien inicia sesion a mitad de
    la compra: Django rota la clave de sesion, pero el visitante es el mismo."""

    def setUp(self):
        self.url = reverse('analitica:registrar_eventos')

    def _enviar(self, nombre='page_view', **extra):
        return self.client.post(self.url, {'eventos': json.dumps([{'nombre': nombre}])}, **extra)

    def test_el_mismo_visitante_conserva_su_identificador_al_iniciar_sesion(self):
        usuario = get_user_model().objects.create_user(
            email='cambia@example.com', username='cambia', password='secret123',
        )
        self._enviar()
        clave_antes = self.client.session.session_key
        self.client.force_login(usuario)
        self.assertNotEqual(self.client.session.session_key, clave_antes)  # la clave si rota
        self._enviar('add_to_cart')

        antes, despues = EventoAnalitica.objects.order_by('creado').values_list('sesion', flat=True)
        self.assertEqual(antes, despues)
        self.assertTrue(EventoAnalitica.objects.filter(nombre='add_to_cart', autenticado=True).exists())
        self.assertEqual(usuario.email, 'cambia@example.com')

    def test_dos_visitantes_distintos_tienen_identificadores_distintos(self):
        self._enviar()
        otro = self.client_class()
        otro.post(self.url, {'eventos': json.dumps([{'nombre': 'page_view'}])})
        sesiones = set(EventoAnalitica.objects.values_list('sesion', flat=True))
        self.assertEqual(len(sesiones), 2)

    def test_el_identificador_no_es_la_clave_de_sesion_ni_el_valor_guardado(self):
        self._enviar()
        evento = EventoAnalitica.objects.get()
        visitante = self.client.session['analitica_vid']
        self.assertNotIn(visitante, evento.sesion)
        self.assertNotEqual(evento.sesion, self.client.session.session_key)

    def test_do_not_track_no_guarda_nada(self):
        respuesta = self._enviar(HTTP_DNT='1')
        self.assertEqual(respuesta.json(), {'ok': True, 'guardados': 0})
        self.assertFalse(EventoAnalitica.objects.exists())

    def test_global_privacy_control_tambien_se_respeta(self):
        self._enviar(HTTP_SEC_GPC='1')
        self.assertFalse(EventoAnalitica.objects.exists())


class EventosDeServidorTests(TestCase):
    def setUp(self):
        self.url = reverse('analitica:registrar_eventos')

    def test_el_cliente_no_puede_fabricar_un_pedido_en_el_embudo(self):
        self.client.post(self.url, {'eventos': json.dumps([{'nombre': 'order_created'}])})
        self.assertFalse(EventoAnalitica.objects.filter(nombre='order_created').exists())

    def test_el_servidor_si_registra_sus_propios_eventos(self):
        from analitica.services import registrar_evento
        peticion = self.client.get(reverse('home')).wsgi_request
        evento = registrar_evento(peticion, 'order_created', valor=1500.0, articulos=2)
        self.assertEqual(evento.nombre, 'order_created')
        self.assertEqual(evento.propiedades, {'valor': 1500.0, 'articulos': 2})
        self.assertRegex(evento.sesion, r'^[0-9a-f]{32}$')

    def test_un_nombre_que_no_es_de_servidor_se_rechaza(self):
        from analitica.services import registrar_evento
        peticion = self.client.get(reverse('home')).wsgi_request
        self.assertIsNone(registrar_evento(peticion, 'page_view'))
        self.assertFalse(EventoAnalitica.objects.exists())

    def test_el_servidor_respeta_do_not_track(self):
        from analitica.services import registrar_evento
        peticion = self.client.get(reverse('home'), HTTP_DNT='1').wsgi_request
        self.assertIsNone(registrar_evento(peticion, 'order_created', valor=1))
        self.assertFalse(EventoAnalitica.objects.exists())

    def test_un_fallo_al_medir_nunca_propaga(self):
        from unittest.mock import patch

        from analitica.services import registrar_evento
        peticion = self.client.get(reverse('home')).wsgi_request
        with patch('analitica.services.EventoAnalitica.objects.create', side_effect=RuntimeError('db')):
            with self.assertLogs('analitica.services', level='ERROR'):
                self.assertIsNone(registrar_evento(peticion, 'order_created', valor=1))
