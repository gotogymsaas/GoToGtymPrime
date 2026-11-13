"""Idiomas, politicas y medicion del asistente."""
import json
import re
from html import unescape
from html.parser import HTMLParser

from analitica.models import EventoAnalitica
from django.test import TestCase, override_settings
from django.urls import reverse

from gotogym import politicas_contenido as politicas_es
from gotogym import politicas_contenido_en as politicas_en

ACENTOS = re.compile(r'[áéíóúñ¿¡ÁÉÍÓÚÑ]')
PALABRAS_EN_ESPANOL = re.compile(
    r'\b(asistente|enviar|reintentar|entendido|carrito|persona|mensaje|conversaci[oó]n|hablar|agregar|agregado|sugerencias|pensando)\b',
    re.IGNORECASE,
)
OMITIR = {'script', 'style', 'noscript', 'svg', 'head', 'title'}


class _Textos(HTMLParser):
    """Texto visible y atributos que se leen en voz alta, de un fragmento."""

    def __init__(self):
        super().__init__()
        self.pila, self.textos = [], []

    def handle_starttag(self, etiqueta, atributos):
        if etiqueta in OMITIR:
            self.pila.append(etiqueta)
        for clave, valor in atributos:
            if clave in ('placeholder', 'aria-label', 'title', 'alt') and valor:
                self.textos.append(valor)

    def handle_endtag(self, etiqueta):
        if self.pila and self.pila[-1] == etiqueta:
            self.pila.pop()

    def handle_data(self, datos):
        if not self.pila and datos.strip():
            self.textos.append(datos.strip())


def _textos(html):
    parser = _Textos()
    parser.feed(html)
    return parser.textos


def _fragmentos_del_asistente(html):
    """El panel y los dos botones que lo abren."""
    panel = html[html.index('class="gtg-vendedor__scrim"'):html.index('</aside>') + len('</aside>')]
    barra = html[html.index('class="gtg-vendedor-toggle"'):]
    barra = barra[:barra.index('</button>') + len('</button>')]
    menu = html[html.index('id="mobile-menu"'):]
    menu = menu[menu.index('<button type="button" class="gtg-vendedor-menu-item"'):]
    menu = menu[:menu.index('</button>') + len('</button>')]
    return panel + barra + menu


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100)
class IdiomasTests(TestCase):
    def test_en_ingles_el_asistente_no_tiene_texto_en_espanol(self):
        html = self.client.get('/en/').content.decode()

        textos = _textos(_fragmentos_del_asistente(html))

        self.assertGreater(len(textos), 25)
        for texto in textos:
            with self.subTest(texto=texto[:60]):
                self.assertIsNone(ACENTOS.search(texto), texto)
                self.assertIsNone(PALABRAS_EN_ESPANOL.search(texto), texto)

    def test_en_espanol_el_asistente_sigue_en_espanol(self):
        html = self.client.get('/es/').content.decode()

        texto = ' '.join(_textos(_fragmentos_del_asistente(html)))

        self.assertIn('Quantum Coach', texto)
        self.assertIn('Estoy contigo.', texto)
        self.assertIn('Soy una IA y puedo equivocarme', texto)
        self.assertIn('Reintentar', texto)

    def test_traducciones_clave(self):
        html = self.client.get('/en/').content.decode()

        for esperado in (
            "Open Quantum Coach, GoToGym's AI", "I’m here with you.", 'Try again', 'Talk to a person',
            'Start a new conversation', 'Added to your cart.', 'Quantum Coach is thinking…',
            "I'm an AI and I can make mistakes", 'I want something to train in',
            'Which size suits me?', 'How does shipping work?',
        ):
            with self.subTest(esperado=esperado):
                self.assertIn(esperado, html)

    def test_la_configuracion_del_idioma_llega_al_endpoint(self):
        html = self.client.get('/en/').content.decode()
        configuracion = json.loads(re.search(r'id="vendedor-config" type="application/json">(.*?)</script>', html, re.S).group(1))

        self.assertEqual(configuracion['endpoint'], '/en/vendedor/mensaje/')
        self.assertEqual(configuracion['cartUrl'], '/en/carrito/')

    def test_las_acciones_del_servidor_salen_en_el_idioma_del_visitante(self):
        from decimal import Decimal

        from .test_utilidades import aislar_catalogo, crear_producto

        aislar_catalogo()
        _, (variante,) = crear_producto('Leggins', [('M', 'gris', 3, {'price_override': Decimal('1000')})])

        respuesta = self.client.post(
            '/en/vendedor/mensaje/', data=json.dumps({'message': 'hola'}),
            content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        etiquetas = {a['type']: a['label'] for a in respuesta.json()['actions']}
        self.assertEqual(etiquetas['add_to_cart'], 'Add M · gris to cart')
        self.assertTrue(etiquetas['open_product'].startswith('View '))
        self.assertTrue(respuesta.json()['actions'][0]['url'].startswith('/en/'))
        self.assertEqual(variante.size, 'M')


class PoliticasTests(TestCase):
    # Cada pagina de politica con la primera frase de su seccion del Coach: el
    # nombre "Quantum Coach" solo no sirve de marca, porque tambien esta en el
    # menu de toda la tienda cuando el Coach esta activo.
    RUTAS = {
        'tratamiento': ('politica_tratamiento_datos', 'TRATAMIENTO_DATOS'),
        'privacidad': ('politica_privacidad', 'PRIVACIDAD'),
    }

    def _pagina(self, ruta, idioma):
        return unescape(self.client.get(f'/{idioma}{reverse(ruta)[3:]}').content.decode())

    def _frase(self, idioma, clave):
        modulo = politicas_en if idioma == 'en' else politicas_es
        return modulo.ASISTENTE_IA[clave]['paragraphs'][0][:60]

    @override_settings(VENDEDOR_ENABLED=False)
    def test_apagado_las_politicas_no_mencionan_el_coach(self):
        for nombre, (ruta, clave) in self.RUTAS.items():
            for idioma in ('es', 'en'):
                with self.subTest(politica=nombre, idioma=idioma):
                    self.assertNotIn(self._frase(idioma, clave), self._pagina(ruta, idioma))

    @override_settings(VENDEDOR_ENABLED=True)
    def test_encendido_las_politicas_explican_que_se_envia(self):
        for nombre, (ruta, clave) in self.RUTAS.items():
            for idioma in ('es', 'en'):
                with self.subTest(politica=nombre, idioma=idioma):
                    self.assertIn(self._frase(idioma, clave), self._pagina(ruta, idioma))

    @override_settings(VENDEDOR_ENABLED=True)
    def test_el_texto_dice_lo_que_si_y_lo_que_no_se_envia(self):
        es = ' '.join(politicas_es.ASISTENTE_IA['TRATAMIENTO_DATOS']['paragraphs'])
        en = ' '.join(politicas_en.ASISTENTE_IA['TRATAMIENTO_DATOS']['paragraphs'])

        for esperado in ('texto de tu mensaje', 'carrito', 'seudonimizado', 'correo electrónico, teléfono, documento de identidad, dirección ni datos de pago',
                         'no guarda el texto de tus mensajes', politicas_es.CORREO_PRIVACIDAD):
            with self.subTest(esperado=esperado):
                self.assertIn(esperado, es)
        for esperado in ('text of your message', 'cart', 'pseudonymized', 'email, phone number, ID document, address and payment details',
                         'does not keep the text of your messages', politicas_es.CORREO_PRIVACIDAD):
            with self.subTest(esperado=esperado):
                self.assertIn(esperado, en)

    def test_la_seccion_en_ingles_no_tiene_espanol(self):
        for seccion in politicas_en.ASISTENTE_IA.values():
            for parrafo in [seccion['title'], *seccion['paragraphs']]:
                with self.subTest(parrafo=parrafo[:50]):
                    self.assertIsNone(ACENTOS.search(parrafo))

    @override_settings(VENDEDOR_ENABLED=True)
    def test_las_demas_politicas_no_cambian(self):
        for ruta in ('politica_cambios', 'politica_envios', 'politica_cookies'):
            with self.subTest(ruta=ruta):
                html = unescape(self.client.get(reverse(ruta)).content.decode())
                for clave in ('TRATAMIENTO_DATOS', 'PRIVACIDAD'):
                    self.assertNotIn(politicas_es.ASISTENTE_IA[clave]['paragraphs'][0][:60], html)


class MedicionTests(TestCase):
    EVENTOS = ['vendedor_open', 'vendedor_message', 'vendedor_product_click',
               'vendedor_add_to_cart', 'vendedor_handoff', 'vendedor_error']

    def setUp(self):
        self.client.cookies['gtg_cookies'] = 'analitica'
        self.url = reverse('analitica:registrar_eventos')

    def _enviar(self, eventos):
        return self.client.post(self.url, {'eventos': json.dumps(eventos)})

    def test_los_eventos_del_asistente_se_guardan(self):
        respuesta = self._enviar([{'nombre': nombre, 'ruta': '/es/tienda/', 'propiedades': {'turno': 1}}
                                  for nombre in self.EVENTOS])

        self.assertEqual(respuesta.json()['guardados'], len(self.EVENTOS))
        self.assertEqual(
            set(EventoAnalitica.objects.values_list('nombre', flat=True)), set(self.EVENTOS),
        )

    def test_un_evento_del_asistente_no_declarado_se_descarta(self):
        respuesta = self._enviar([{'nombre': 'vendedor_texto_del_mensaje', 'propiedades': {}}])

        self.assertEqual(respuesta.json()['guardados'], 0)

    def test_sin_consentimiento_no_se_guarda_nada(self):
        self.client.cookies['gtg_cookies'] = 'necesarias'

        respuesta = self._enviar([{'nombre': 'vendedor_message', 'propiedades': {}}])

        self.assertEqual(respuesta.json()['guardados'], 0)
        self.assertFalse(EventoAnalitica.objects.exists())

    def test_las_propiedades_largas_se_recortan(self):
        # Red de seguridad: aunque el navegador mandara texto largo, no se guarda entero.
        self._enviar([{'nombre': 'vendedor_message', 'propiedades': {'texto': 'x' * 5000}}])

        guardado = EventoAnalitica.objects.get(nombre='vendedor_message')

        self.assertLessEqual(len(guardado.propiedades['texto']), 120)
