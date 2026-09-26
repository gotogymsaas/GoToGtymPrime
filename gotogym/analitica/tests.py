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
